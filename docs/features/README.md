# Overview

Besides Connaisseur's central functionality, several additional features are available:

- [Metrics](./metrics.md): *get prometheus metrics at `/metrics`*
- [Alerting](./alerting.md): *send alerts based on verification result*
- [Detection Mode](./detection_mode.md): *warn but do not block invalid images*
- [Validation Mode](./validation_mode.md): *configure whether or not to mutate images*
- [Namespaced Validation](./namespaced_validation.md): *restrict validation to dedicated namespaces*
- [Automatic Child Approval](automatic_child_approval.md): *configure approval of Kubernetes child resources*

In combination, these features help to improve usability and might better support the DevOps workflow.
Switching Connaisseur to _detection mode_ and alerting on non-compliant images can for example avoid service interruptions while still benefitting from improved supply-chain security.

Feel free to [propose new features](https://github.com/sse-secure-systems/connaisseur/issues/new?assignees=&labels=&template=feature_request.md&title=) that would make Connaisseur an even better experience :hammer_pick:

