package feedback

import (
	"bytes"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"gopkg.in/yaml.v2"
	"io/ioutil"
	"net/http"
	"net/url"
)

type TapRequestHeader struct {
	Name       string `yaml:"name"`
	RegexMatch string `yaml:"regex_match"`
}

type TapSink struct {
	StreamingAdmin map[string]string `yaml:"streaming_admin"`
}

type TapRequest struct {
	ConfigID  string `yaml:"config_id"`
	TapConfig struct {
		MatchConfig struct {
			HttpRequestHeadersMatch struct {
				Headers []TapRequestHeader `yaml:"headers"`
			} `yaml:"http_request_headers_match"`
		} `yaml:"match_config"`
		OutputConfig struct {
			Sinks []TapSink `yaml:"sinks"`
		} `yaml:"output_config"`
	} `yaml:"tap_config"`
}

type Trace struct {
	Headers []struct {
		Key   string `json:"key"`
		Value string `json:"value"`
	} `json:"headers"`
	Body struct {
		Truncated bool   `json:"truncated"`
		AsBytes   string `json:"as_bytes"`
	} `json:"body"`
}

type Message struct {
	HttpBufferedTrace struct {
		Request  Trace `json:"request,omitempty"`
		Response Trace `json:"response,omitempty"`
	} `json:"http_buffered_trace"`
}

type RequestCollector struct {
	feedbackRequest *TapRequest
	envoyHost       string
	logger          DataLogging
}

func NewRequestCollector(envoyHost string, configId string, logger DataLogging) *RequestCollector {
	feedbackRequest := TapRequest{
		ConfigID: configId,
	}
	feedbackRequest.TapConfig.MatchConfig.HttpRequestHeadersMatch.Headers =
		append(
			feedbackRequest.TapConfig.MatchConfig.HttpRequestHeadersMatch.Headers,
			TapRequestHeader{Name: ":path", RegexMatch: ".*/api/model/invoke.*"},
		)
	feedbackRequest.TapConfig.OutputConfig.Sinks = append(
		feedbackRequest.TapConfig.OutputConfig.Sinks,
		TapSink{StreamingAdmin: map[string]string{}},
	)

	return &RequestCollector{
		feedbackRequest: &feedbackRequest,
		envoyHost:       envoyHost,
		logger:          logger,
	}
}

func parseUrlencodedParams(params url.Values) map[string]interface{} {
	args := make(map[string]interface{}, len(params))

	for k, v := range params {
		if len(v) == 1 {
			args[k] = v[0]
		} else {
			args[k] = v
		}
	}

	return args
}

func convertToFeedback(message *Message) (*RequestResponse, *ResponseBody) {
	responseBody := &ResponseBody{}
	requestResponse := &RequestResponse{}

	requestHeaders := make(map[string]string, len(message.HttpBufferedTrace.Request.Headers))
	for _, header := range message.HttpBufferedTrace.Request.Headers {
		switch header.Key {
		case RequestIdHeaderKey:
			responseBody.RequestID = header.Value
			requestResponse.RequestID = header.Value

		case HttpMethodHeaderKey:
			requestResponse.RequestHttpMethod = header.Value

		case OriginalUriHeaderKey:
			requestResponse.RequestUri = header.Value

		case ForwardedHostHeaderKey:
			requestResponse.RequestHost = header.Value
		}

		requestHeaders[header.Key] = header.Value
	}

	responseHeaders := make(map[string]string, len(message.HttpBufferedTrace.Response.Headers))
	for _, header := range message.HttpBufferedTrace.Response.Headers {
		switch header.Key {
		case ModelNameHeaderKey:
			responseBody.ModelName = header.Value
			requestResponse.ModelName = header.Value

		case ModelVersionHeaderKey:
			responseBody.ModelVersion = header.Value
			requestResponse.ModelVersion = header.Value

		case ModelEndpointHeaderKey:
			responseBody.ModelEndpoint = header.Value
			requestResponse.ModelEndpoint = header.Value

		case StatusHeaderKey:
			requestResponse.ResponseStatus = header.Value
		}

		responseHeaders[header.Key] = header.Value
	}

	requestResponse.RequestHttpHeaders = requestHeaders
	requestResponse.ResponseHttpHeaders = responseHeaders

	responseBytes, err := base64.StdEncoding.DecodeString(message.HttpBufferedTrace.Response.Body.AsBytes)
	if err != nil {
		// Impossible situation
		panic(err)
	}
	responseBody.ResponseContent = string(responseBytes)

	if requestResponse.RequestHttpMethod == "GET" {
		uri, err := url.ParseRequestURI(requestResponse.RequestUri)
		if err == nil {
			requestResponse.RequestGetArgs = parseUrlencodedParams(uri.Query())
		}
	} else {
		requestBytes, err := base64.StdEncoding.DecodeString(message.HttpBufferedTrace.Request.Body.AsBytes)
		if err != nil {
			// Impossible situation
			panic(err)
		}
		params, err := url.ParseQuery(string(requestBytes))
		if err == nil {
			requestResponse.RequestPostArgs = parseUrlencodedParams(params)
		}
	}

	return requestResponse, responseBody
}

func (rc *RequestCollector) TraceRequests() error {
	feedbackRequestYaml, err := yaml.Marshal(rc.feedbackRequest)
	if err != nil {
		panic(err)
	}
	fmt.Println(string(feedbackRequestYaml))

	req := &http.Request{
		Method: "POST",
		URL: &url.URL{
			Scheme: "http",
			Host:   rc.envoyHost,
			Path:   "/tap",
		},
		Body: ioutil.NopCloser(bytes.NewBuffer(feedbackRequestYaml)),
	}
	client := &http.Client{
		Transport: http.DefaultTransport,
		Timeout:   0,
	}

	resp, err := client.Do(req)

	if err != nil {
		return err
	}

	dec := json.NewDecoder(resp.Body)
	for dec.More() {
		var message Message

		err := dec.Decode(&message)
		if err != nil {
			return err
		}

		requestResponse, responseBody := convertToFeedback(&message)

		err = rc.logger.Post(RequestResponseTag, *requestResponse)
		if err != nil {
			return err
		}

		err = rc.logger.Post(ResponseBodyTag, *responseBody)
		if err != nil {
			return err
		}
	}

	return err
}
