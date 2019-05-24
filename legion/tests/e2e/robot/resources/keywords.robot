*** Settings ***
Documentation       Legion robot resources
Resource            variables.robot
Variables           ../load_variables_from_profiles.py
Library             String
Library             OperatingSystem
Library             Collections
Library             DateTime
Library             legion.robot.libraries.k8s.K8s  ${LEGION_NAMESPACE}
Library             legion.robot.libraries.utils.Utils
Library             legion.robot.libraries.grafana.Grafana
Library             legion.robot.libraries.process.Process
Library             legion.robot.libraries.edi.EDI  ${EDI_URL}  ${DEX_TOKEN}

*** Keywords ***
Shell
    [Arguments]           ${command}
    ${result}=            Run Process without PIPE   ${command}    shell=True
    Log                   stdout = ${result.stdout}
    Log                   stderr = ${result.stderr}
    [Return]              ${result}

StrictShell
    [Arguments]           ${command}
    ${res}=   Shell  ${command}
              Should Be Equal  ${res.rc}  ${0}
    [Return]  ${res}

FailedShell
    [Arguments]           ${command}
    ${res}=   Shell  ${command}
              Should Not Be Equal  ${res.rc}  ${0}
    [Return]  ${res}

Connect to main Grafana
    Connect to Grafana    ${GRAFANA_URL}  ${GRAFANA_USER}  ${GRAFANA_PASSWORD}

Build model
    [Arguments]  ${mt_name}  ${model_name}  ${model_version}  ${model_image_key_name}=\${TEST_MODEL_IMAGE}  ${entrypoint}=simple.py  ${kwargs}=&{EMPTY}

    ${args}=  prepare stub args  ${kwargs}
    StrictShell  legionctl --verbose mt delete ${mt_name} --ignore-not-found
    StrictShell  legionctl --verbose mt create ${mt_name} --toolchain-type python --vcs ${TEST_VCS} --workdir legion/tests/e2e/models --entrypoint=${entrypoint} -a '--name ${model_name} --version ${model_version} ${args}'

    ${mt}=  get model training  ${mt_name}

    Set Suite Variable  ${model_image_key_name}  ${mt.trained_image}

    # --------- DEPLOY COMMAND SECTION -----------
Run EDI deploy
    [Documentation]  run legionctl 'deploy command', logs result and return dict with return code and output(for exceptions)
    [Arguments]           ${name}  ${image}  ${role_name}
    ${result}=            Run Process without PIPE   legionctl --verbose md create ${name} --image ${image} --role ${role_name}  shell=True
    Log                   stdout = ${result.stdout}
    Log                   stderr = ${result.stderr}
    [Return]              ${result}

Run EDI deploy and check model started
    [Arguments]           ${name}     ${image}      ${model_name}   ${model_ver}  ${role_name}=${EMPTY}
    ${edi_state}=   Shell  legionctl --verbose md create ${name} --image ${image} --role "${role_name}"
    Should Be Equal As Integers          ${edi_state.rc}         0
    ${response}=    Wait Until Keyword Succeeds  1m  0 sec  Check model started  ${name}
    Should contain                       ${response}             'model_name': '${model_name}'
    Should contain                       ${response}             'model_version': '${model_ver}'

    # --------- UNDEPLOY COMMAND SECTION -----------
Run EDI undeploy model and check
    [Arguments]           ${md_name}
    ${edi_state}=                Shell  legionctl --verbose md delete ${md_name} --ignore-not-found
    Should Be Equal As Integers  ${edi_state.rc}        0
    ${edi_state} =               Shell  legionctl --verbose md get
    Should Be Equal As Integers  ${edi_state.rc}        0
    Should not contain           ${edi_state.stdout}    ${md_name}

# --------- OTHER KEYWORDS SECTION -----------

Get token from EDI
    [Documentation]  get token from EDI for the EDGE session
    [Arguments]           ${md_name}  ${role}=${EMPTY}
    ${resp} =             Shell  legionctl generate-token --md ${md_name} --role "${role}"
    Should be equal as integers       ${resp.rc}  0
    Set Suite Variable    ${TOKEN}   ${resp.stdout}
    [Return]              ${resp.stdout}

Check model started
    [Documentation]  check if model run in container by http request
    [Arguments]           ${md_name}
    ${resp}=              Shell  legionctl --verbose model info --md ${md_name}
    Should be equal       ${resp.rc}  ${0}
    Log                   ${resp.stdout}
    Should not be empty   ${resp.stdout}
    [Return]              ${resp.stdout}

Verify model info from edi
    [Arguments]      ${target_model}       ${model_name}        ${model_state}      ${model_replicas}
    Should Be Equal  ${target_model[0]}    ${model_name}        invalid model name
    Should Be Equal  ${target_model[1]}    ${model_state}       invalid model state
    Should Be Equal  ${target_model[2]}    ${model_replicas}    invalid model replicas
    # --------- TEMPLATE KEYWORDS SECTION -----------

Check if component domain has been secured
    [Arguments]     ${component}    ${enclave}
    [Documentation]  Check that a legion component is secured by auth
    &{response} =    Run Keyword If   '${enclave}' == '${EMPTY}'    Get component auth page    ${HOST_PROTOCOL}://${component}.${HOST_BASE_DOMAIN}
    ...    ELSE      Get component auth page    ${HOST_PROTOCOL}://${component}-${enclave}.${HOST_BASE_DOMAIN}
    Log              Auth page for ${component} is ${response}
    Dictionary Should Contain Item    ${response}    response_code    200
    ${auth_page} =   Get From Dictionary   ${response}    response_text
    Should contain   ${auth_page}    Log in

Secured component domain should not be accessible by invalid credentials
    [Arguments]     ${component}    ${enclave}
    [Documentation]  Check that a secured legion component does not provide access by invalid credentials
    &{creds} =       Create Dictionary 	login=admin   password=admin
    &{response} =    Run Keyword If   '${enclave}' == '${EMPTY}'    Post credentials to auth    ${HOST_PROTOCOL}://${component}    ${HOST_BASE_DOMAIN}    ${creds}
    ...    ELSE      Post credentials to auth    ${HOST_PROTOCOL}://${component}-${enclave}     ${HOST_BASE_DOMAIN}    ${creds}
    Log              Bad auth page for ${component} is ${response}
    Dictionary Should Contain Item    ${response}    response_code    200
    ${auth_page} =   Get From Dictionary   ${response}    response_text
    Should contain   ${auth_page}    Log in to Your Account
    Should contain   ${auth_page}    Invalid Email Address and password

Secured component domain should be accessible by valid credentials
    [Arguments]     ${component}    ${enclave}
    [Documentation]  Check that a secured legion component does not provide access by invalid credentials
    &{creds} =       Create Dictionary    login=${STATIC_USER_EMAIL}    password=${STATIC_USER_PASS}
    &{response} =    Run Keyword If   '${enclave}' == '${EMPTY}'    Post credentials to auth    ${HOST_PROTOCOL}://${component}    ${HOST_BASE_DOMAIN}    ${creds}
    ...    ELSE      Post credentials to auth    ${HOST_PROTOCOL}://${component}-${enclave}     ${HOST_BASE_DOMAIN}    ${creds}
    Log              Bad auth page for ${component} is ${response}
    Dictionary Should Contain Item    ${response}    response_code    200
    ${auth_page} =   Get From Dictionary   ${response}    response_text
    Should contain   ${auth_page}    ${component}
    Should not contain   ${auth_page}    Invalid Email Address and password

Login to the edi and edge
    ${res}=  Shell  legionctl --verbose login --edi ${EDI_URL} --token "${DEX_TOKEN}"
    Should be equal  ${res.rc}  ${0}
    ${res}=  Shell  legionctl config set MODEL_HOST ${EDGE_URL}
    Should be equal  ${res.rc}  ${0}