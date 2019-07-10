//
//    Copyright 2019 EPAM Systems
//
//    Licensed under the Apache License, Version 2.0 (the "License");
//    you may not use this file except in compliance with the License.
//    You may obtain a copy of the License at
//
//        http://www.apache.org/licenses/LICENSE-2.0
//
//    Unless required by applicable law or agreed to in writing, software
//    distributed under the License is distributed on an "AS IS" BASIS,
//    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
//    See the License for the specific language governing permissions and
//    limitations under the License.
//

package v1alpha1

import (
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
)

const (
	S3Type = "s3"
)

// DataBindingSpec defines the desired state of DataBinding
type DataBindingSpec struct {
	// blabla
	// +kubebuilder:validation:Enum=s3
	Type string `json:"type"`
	// blabla
	URI string `json:"uri"`
	// blabla
	Region string `json:"region,omitempty"`
}

// DataBindingStatus defines the observed state of DataBinding
type DataBindingStatus struct {
}

// +genclient
// +k8s:deepcopy-gen:interfaces=k8s.io/apimachinery/pkg/runtime.Object

// DataBinding is the Schema for the databindings API
// +k8s:openapi-gen=true
type DataBinding struct {
	metav1.TypeMeta   `json:",inline"`
	metav1.ObjectMeta `json:"metadata,omitempty"`

	Spec   DataBindingSpec   `json:"spec,omitempty"`
	Status DataBindingStatus `json:"status,omitempty"`
}

// +k8s:deepcopy-gen:interfaces=k8s.io/apimachinery/pkg/runtime.Object

// DataBindingList contains a list of DataBinding
type DataBindingList struct {
	metav1.TypeMeta `json:",inline"`
	metav1.ListMeta `json:"metadata,omitempty"`
	Items           []DataBinding `json:"items"`
}

func init() {
	SchemeBuilder.Register(&DataBinding{}, &DataBindingList{})
}
