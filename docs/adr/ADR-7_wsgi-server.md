# ADR 7: WSGI Server

## Status

Accepted

## Context

We were running the Flask WSGI application with the built-in Flask server, which is not meant for production. Problems are mainly due to potential debug shell on the server and single thread in default configuration. Both were mitigated in our setup, but we decided to test a proper WSGI server at some point. Especially the log entry

```text
 * Serving Flask app 'connaisseur.flask_server' (lazy loading)
 * Environment: production
   WARNING: This is a development server. Do not use it in a production deployment.
   Use a production WSGI server instead.
```
did cause anguish among users, see e.g. [issue 11](https://github.com/sse-secure-systems/connaisseur/issues/11).

## Considered options

### Choice 1: WSGI server

There's plenty of WSGI server around and the question poses itself, which one to pick. Flask itself has a [list of servers](https://flask.palletsprojects.com/en/1.1.x/deploying/), there's comparisons around, for example [here](https://medium.com/django-deployment/which-wsgi-server-should-i-use-a70548da6a83) and [here](https://www.appdynamics.com/blog/engineering/a-performance-analysis-of-python-wsgi-servers-part-2/). The choice, which WSGI servers to test was somewhat arbitrary among better performing ones in the posts.

Contenders were Bjoern, Cheroot, Flask, Gunicorn and uWSGI. Bjoern was immediately dropped, since it worked only with Python2. Later, during testing Bjoern did support Python3, but no TLS, so we stuck to dropping it. Gunicorn was tested for a bit, but since it delivered worse results than the others and it requires a writable `worker-tmp-dir` directory, it was also dropped from contention.

The remaining three were tested over a rather long time of development, i.e. from before the first bit of validation parallelization to after the 2.0 release. All tests were run on local minikube/kind clusters with rather constrained resources in the expectation that this will still provide reasonable insight into the servers' behavior on regular production clusters.

#### Test results
Since the results span a longer timeframe and at least at first performed to find some way to distinguish the servers instead of having a clear plan, some tests feature a different configuration. If not specified different Cheroot was run with default configuration (minimum number of threads 10, no maximum limit), Flask in its default configuration and uWSGI with 2 processes and 1 thread (low because it already has a bigger footprint when idle to begin with). Connaisseur itself was configured with its default of 3 pods.

##### Integration test
###### Before parallelization
Before paralellization was ever implemented, there were tests running the integration test on the cluster and seeing how often the test failed.

The error rate across 50 executions was 8% (4/50) for Cheroot, 22% (11/50) for Flask and 12% (6/50) for uWSGI. These error rates could be as high because the non-parallelized fetching of notary trust data regularly took around 25 seconds with a maximum timeout of 30 seconds.

###### With simple parallelization
After parallelization (of fetching base trust data) was added, the tests were rerun. This time all 50 checks for all servers were run together with randomized order of servers for each of the 50 test runs.

Error rates were 4% (2/50) for Cheroot and 6% (3/50) for uWSGI. Flask was not tested.

##### Stress tests
###### Complex requests
There was a test setup with complex individual requests containing multiple different initContainers and containers or many instantiations of a particular image.

The test was performed using `kubectl apply -f loadtest.yaml` on the below file.
<details>
<summary>loadtest.yaml</summary>
<pre>
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis-with-many-instances
  labels:
    app: redis
    loadtest: loadtest
spec:
  selector:
    matchLabels:
      app: redis
  replicas: 1000
  template:
    metadata:
      labels:
        app: redis
    spec:
      containers:
      - name: redis
        image: redis

---

apiVersion: v1
kind: Pod
metadata:
  name: pod-with-many-containers
  labels:
    loadtest: loadtest
spec:
  containers:
  - name: container1
    image: busybox
    command: ['sh', '-c', 'sleep 3600']
  - name: container2
    image: redis
  - name: container3
    image: node
  - name: container4
    image: nginx
  - name: container5
    image: rabbitmq
  - name: container6
    image: elasticsearch
  - name: container7
    image: sonarqube

---

apiVersion: v1
kind: Pod
metadata:
  name: pod-with-many-containers-and-init-containers
  labels:
    loadtest: loadtest
spec:
  containers:
  - name: container1
    image: busybox
    command: ['sh', '-c', 'sleep 3600']
  - name: container2
    image: redis
  - name: container3
    image: node
  - name: container4
    image: nginx
  - name: container5
    image: rabbitmq
  - name: container6
    image: elasticsearch
  - name: container7
    image: sonarqube
  initContainers:
  - name: init2
    image: maven
  - name: init3
    image: vault
  - name: init4
    image: postgres

---

apiVersion: v1
kind: Pod
metadata:
  name: pod-with-some-containers-and-init-containers
  labels:
    loadtest: loadtest
spec:
  containers:
  - name: container1
    image: busybox
    command: ['sh', '-c', 'sleep 3600']
  - name: container2
    image: redis
  - name: container3
    image: node
  - name: container4
    image: nginx
  initContainers:
  - name: container5
    image: rabbitmq
  - name: container6
    image: elasticsearch
  - name: container7
    image: sonarqube

---

apiVersion: v1
kind: Pod
metadata:
  name: pod-with-coinciding-containers-and-init-containers
  labels:
    loadtest: loadtest
spec:
  containers:
  - name: container1
    image: busybox
    command: ['sh', '-c', 'sleep 3600']
  - name: container2
    image: redis
  - name: container3
    image: node
  initContainers:
  - name: init1
    image: busybox
    command: ['sh', '-c', 'sleep 3600']
  - name: init2
    image: redis
  - name: init3
    image: node
</pre>
</details>

None of the servers regularly managed to pass this particular loadtest. However, the pods powered by the Flask server regularly died and had to be restarted, whereas both Cheroot and uWSGI had nearly no restarts and never on all instances. uWSGI seldomly even managed to pass the test.

##### Less complex requests with some load
Since in the above the most complex request was the bottleneck, we tried an instance of the test with less complexity in the individual requests but more requests instead. However, that led to no real distinguishing behaviour across the servers.

##### Load test
To check the servers behaviour when hit with lots of (easy) requests at the same time, we also implemented an actual load test. We ran `parallel --jobs 20 ./testn.sh {1} :::: <(seq 200)` and `parallel --jobs 50 ./testn.sh {1} :::: <(seq 200)` with the below files.

<details>
<summary>File contents</summary>
testn.sh
<pre>
nr=$1

tmpf=$(mktemp)
filec=$(nr=${nr} envsubst <loadtest3.yaml >${tmpf})

kubectl apply -f ${tmpf}
</pre>
loadtest3.yaml
<pre>
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis-${nr}
  labels:
    app: redis
    loadtest: loadtest
spec:
  selector:
    matchLabels:
      app: redis
  replicas: 1
  template:
    metadata:
      labels:
        app: redis
    spec:
      containers:
      - name: redis
        image: redis
</pre>
</details>

Afterwards, we checked how many of the pods were actually created.

| Server                                                |  Created pods (parallel 20 jobs)                                     | Created pods (parallel 50 jobs)           |
| -------------------------------------------------- | ----------------------------------------------------  | ----------------- |
| Cheroot | 173 | 78 |
| Cheroot (numthreads=40) | - | 81 |
| Flask | 173 | 81 |
| uWSGI | 49 | - |
| uWSGI (1 process, 10 threads) | 164 | 35 |
| uWSGI (4 processes, 10 threads) | 146 | 135 |
| uWSGI (1 process, 40 threads) | 164 | 112 |

Interestingly, Flask (narrowly) performs best for this test (for strong load, not for massive load) and for both Cheroot and uWSGI adding further parallelization doesn't necessarily help the stability even when intuitively it should. For 50 jobs in parallel the low creation rate is due to the pods dying at some point during the barrage.

Resource consumption measured via `kubectl top pods -n connaisseur` during the loadtest:

Shown is representative sample from across multiple invocations only at 20 jobs, since for 50 jobs most often the pods died and metrics API is slow to give accurate information after restart.

Cheroot
```
NAME                                      CPU(cores)   MEMORY(bytes)
connaisseur-deployment-644458d686-2tfjp   331m         46Mi
connaisseur-deployment-644458d686-kfzdq   209m         44Mi
connaisseur-deployment-644458d686-t57lp   321m         53Mi
```

Flask
```
NAME                                      CPU(cores)   MEMORY(bytes)
connaisseur-deployment-644458d686-t6c24   381m         42Mi
connaisseur-deployment-644458d686-thgzd   328m         42Mi
connaisseur-deployment-644458d686-wcprp   235m         38Mi
```

uWSGI (1 process, 10 threads)
```
NAME                                     CPU(cores)   MEMORY(bytes)
connaisseur-deployment-d86fbfcd8-9c5m7   129m         63Mi
connaisseur-deployment-d86fbfcd8-hv6sp   309m         67Mi
connaisseur-deployment-d86fbfcd8-w46dz   298m         67Mi
```


#### Option 1.1: Flask

Staying with the Flask server is obviously an option. It doesn't resolve the problem, but it did us a good service and there's no known problems with its usage in practice.

However, the authors discourage using it:

> When running publicly rather than in development, you should not use the built-in development server (flask run). The development server is provided by Werkzeug for convenience, but is not designed to be particularly efficient, stable, or secure. [source](https://flask.palletsprojects.com/en/1.1.x/tutorial/deploy/)

and it performs worst by far for complex requests.


#### Option 1.2: Cheroot
Cheroot performs better than Flask for complex requests and better than uWSGI when under strong load. However, when under massive load, even increasing its minimum number of threads doesn't really add a lot to its stability.

In addition, it seems to be less known and not among the servers that the Flask project lists. On the other hand, its memory footprint is better than uWSGI's and almost on par with Flask's, whereas its CPU footprint is on par with uWSGI and slightly better than the one of Flask.

#### Option 1.2: uWSGI
uWSGI (narrowly) has the best showing for complex requests, but performs worst for strong load. However, if trying to deal with a massive load, scaling its resources allows uWSGI to significantly outperform the other options for very massive load.

Its memory footprint is higher than for Cheroot and Flask, but its CPU footprint is on par with Cheroot and slightly better than Flask's.


#### Decision

We chose option 1.2 and will for now go forward with Cheroot as the WSGI server. The decision was based on the server performing best in the relevant parts of the stress and load tests.
