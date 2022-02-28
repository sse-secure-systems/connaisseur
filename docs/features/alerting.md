# Alerting


Connaisseur can send notifications on admission decisions to basically every REST
endpoint that accepts JSON payloads.

## Supported interfaces

Slack, Opsgenie and Keybase have pre-configured payloads that are ready to use.
However, you can use the existing payload templates as an example how to model your
own custom one.
It is also possible to configure multiple interfaces for receiving
alerts at the same time.

## Configuration options

Currently, Connaisseur supports alerting on either admittance of images, denial of images or both. These event categories can be configured independently of each other under the relevant category (i.e. `admit_request` or `reject_request`):

| Key                                                 |  Accepted values                                      | Default           | Required           | Description                                                                                         |
| --------------------------------------------------- | ----------------------------------------------------- | ----------------- | ------------------ | --------------------------------------------------------------------------------------------------- |
| `alerting.cluster_identifier`                       | string                                                | `"not specified"` |                    | Cluster identifier used in alert payload to distinguish between alerts from different clusters.     |
| `alerting.<category>.template`                      | `opsgenie`, `slack`, `keybase`, `ecs-1-12-0` or custom<sup>*</sup>  | -   | :heavy_check_mark: | File in `helm/alert_payload_templates/` to be used as alert payload template.                       |
| `alerting.<category>.receiver_url`                  | string                                                | -                 | :heavy_check_mark: | URL of alert-receiving endpoint.                                                                    |
| `alerting.<category>.priority`                      | int                                                   | `3`               |                    | Priority of alert (to enable fitting Connaisseur alerts into alerts from other sources).            |
| `alerting.<category>.custom_headers`                | list[string]                                          | -                 |                    | Additional headers required by alert-receiving endpoint.                                            |
| `alerting.<category>.payload_fields`                | subyaml                                               | -                 |                    | Additional (`yaml`) key-value pairs to be appended to alert payload (as `json`).                    |
| `alerting.<category>.fail_if_alert_sending_fails`   | bool                                                  | `False`           |                    | Whether to make Connaisseur deny images if the corresponding alert cannot be successfully sent.     |
| `alerting.<category>.receiver_authentication_type`  | string enum `basic`, `bearer`, `none`                 | `none`            |                    | Authentication type of the alert-receiving webhook endpoint .                                       |
| `alerting.<category>.receiver_authentication_basic`               | object              | -                 | only when `receiver_authentication_type` is `basic`  | Authentication credentials for basic authentication.                                  |
| `alerting.<category>.receiver_authentication_basic.username_env`  | string              | -                 | only when `receiver_authentication_type` is `basic`  | Username Environmental variable for basic authentication.                             |
| `alerting.<category>.receiver_authentication_basic.password_env`  | string              | -                 | only when `receiver_authentication_type` is `basic`  | Password Environmental variable for basic authentication.                             |
| `alerting.<category>.receiver_authentication_basic.authentication_scheme`  | string (without spaces) | `Basic`           |                                         | Prefix for Authorization header for basic authentication.                             |
| `alerting.<category>.receiver_authentication_bearer`              | object              | -                 | only when `receiver_authentication_type` is `bearer` | Authentication credentials for bearer authentication.                                 |
| `alerting.<category>.receiver_authentication_bearer.token_env`    | string              | -                 | only when `receiver_authentication_type` is `bearer` | Token Environmental variable for bearer authentication (Exclusive with `token_file`). |
| `alerting.<category>.receiver_authentication_bearer.token_file`   | string              | -                 | only when `receiver_authentication_type` is `bearer` | Token file for bearer authentication (Exclusive with `token_env`).                    |
| `alerting.<category>.receiver_authentication_bearer.authentication_scheme` | string (without spaces) | `Bearer`         |                                          | Prefix for Authorization header for bearer authentication.                            |

<sup>*basename of the custom template file in `helm/alerting_payload_templates` without file extension </sup>

_Notes_:

- The value for `template` needs to match an existing file of the pattern
`helm/alert_payload_templates/<template>.json`; so if you want to use a predefined
one it needs to be one of `slack`, `keybase`, `opsgenie` or `ecs-1-12-0`.
- For Opsgenie you need to configure an additional
  `["Authorization: GenieKey <Your-Genie-Key>"]` header.
- For [Elastic Common Schema 1.12.0](https://www.elastic.co/guide/en/ecs/1.12/index.html) output, the `receiver_url` has to be an HTTP/S log ingester, such as [Fluentd HTTP input](https://docs.fluentd.org/input/http) or [Logstash HTTP input](https://www.elastic.co/guide/en/logstash/current/plugins-inputs-http.html). Also `custom_headers` needs to be set to `["Content-Type: application/json"]` for Fluentd HTTP endpoints.
- `fail_if_alert_sending_fails` only comes into play for requests that Connaisseur would have admitted as other requests would have been denied in the first place. The setting can come handy if you want to run Connaisseur in detection mode but still make sure that you get notified about what is going on in your cluster. **However, this setting will significantly impact cluster interaction for everyone (i.e. block any cluster change associated to an image) if the alert sending fails permanently, e.g. accidental deletion of your Slack Webhook App, GenieKey expired...**



## Example
For example, if you would like to receive notifications in Keybase whenever Connaisseur admits a request to your cluster, your alerting configuration would look similar to the following snippet:


```
alerting:
  admit_request:
    templates:
      - template: keybase
        receiver_url: https://bots.keybase.io/webhookbot/<Your-Keybase-Hook-Token>
```

## Example With Authentication

For example, if you would like to receive notifications in your custom webhook authenticated with a bearer token taken from an environmental variable whenever Connaisseur admits a request to your cluster, your alerting configuration would look similar to the following snippet:

```
alerting:
  admit_request:
    templates:
      - template: ecs-1-12-0 
        receiver_url: https://your.custom.domain.com/webhook/admit
        receiver_authentication_type: bearer
        receiver_authentication_bearer: 
          token_env: CONNAISSEUR_ADMIT_REQUEST_WEBHOOK_AUTH_TOKEN
```

You then have to set the `CONNAISSEUR_ADMIT_REQUEST_WEBHOOK_AUTH_TOKEN` environment variable referencing the bearer token secret you want to use into the connaisseur deployment.

Or if you would like to use the service account token as the bearer token, you can use the following snippet:

```
alerting:
  admit_request:
    templates:
      - template: ecs-1-12-0 
        receiver_url: https://your.custom.domain.com/webhook/admit
        receiver_authentication_type: bearer
        receiver_authentication_bearer: 
          token_file: /var/run/secrets/kubernetes.io/serviceaccount/token
```

Finally in case of basic authentication, you can use the following snippet:


```
alerting:
  admit_request:
    templates:
      - template: ecs-1-12-0 
        receiver_url: https://your.custom.domain.com/webhook/admit
        receiver_authentication_type: basic
        receiver_authentication_basic: 
          username_env: CONNAISSEUR_ADMIT_REQUEST_WEBHOOK_AUTH_USERNAME
          password_env: CONNAISSEUR_ADMIT_REQUEST_WEBHOOK_AUTH_PASSWORD
```

You then have to set the `CONNAISSEUR_ADMIT_REQUEST_WEBHOOK_AUTH_USERNAME` and `CONNAISSEUR_ADMIT_REQUEST_WEBHOOK_AUTH_PASSWORD` environment variables referencing the secret you want to use into the connaisseur deployment.


## Additional notes

### Creating a custom template

Along the lines of the templates that already exist you can easily define
custom templates for other endpoints. The following variables can be rendered
during runtime into the payload:

- `alert_message`
- `priority`
- `connaisseur_pod_id`
- `cluster`
- `timestamp`
- `request_id`
- `images`

Referring to any of these variables in the templates works by Jinja2 notation
(e.g. `{{ timestamp }}`). You can update your payload dynamically by adding payload
fields in `yaml` representation in the `payload_fields` key which will be translated
to JSON by Helm as is. If your REST endpoint requires particular headers, you can
specify them as described above in `custom_headers`.

Feel free to make a PR to share with the community if you add new neat templates for other third parties :pray:

