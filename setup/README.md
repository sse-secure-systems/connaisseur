# A Connaisseur Setup Guide

## Intro

Hey! Pssst, over here. I got something for you. Image signature verification for Kubernetes, that only allows cryptographically signed images into the cluster as a means to prevent malicious content from entering the system, such as those pesky bitcoin miners. Sounds complicated? It ain't, so let's go!

It all starts with Kubernetes, the thing that is taking the tech world by storm. Everyone is talking about it, everyone is using it and it handles all the important questions such as, *"can we automate it?"*, *"is it scalable?"* and *"do we really wanna use blockchain and/or AI to solve this simple problem?"*. Never has it been easier to deploy your applications. Some yaml files here and there, a container image of the application and maybe some volumes for persistent storage. Boom. You got yourself an application that not only can be scaled up and down in case of request spikes, but also be updated without any downtime, all running on different virtual and/or physical machines, in a distributed way (blockchain: :heavy_check_mark:).

*What a time to be alive*. Or is it? What about security? Is Kubernetes doing anything in regards of security? Well yes it does. There are systems in place such as *RBAC*, so access to different resources can be easily managed, or *Istio* for encrypting internal and external traffic. What about image integrity, the thing that makes sure the running applications doesn't do some bitcoin mining instead of showing our *"Hello World!"* page? No? Well then let's change that!

Entering the scene – **connaisseur**. Making sure only the right images are running in your Kubernetes cluster, since 2020. Running as a mutating admission webhook, that intercepts incoming requests and changes all images found there into their signed versions, if present. Otherwise it denies the request and thus hit the bitcoin miners right where it hurts. For doing so, connaisseur requires a **notary server**, which is an implementation of *The Update Framework*. It stores the actual signatures and information about what exact images to choose.

Now all you need to do is set those two up and you got yourself some image integrity in your Kubernetes cluster. How, you may ask? Well that's what this write-up is for. We shall give you a practical setup guide, that shows how to install notary and connaisseur in your cluster and how to sign all your images, so no more bitcoin mining is possible.

## Setup

### Prerequisites

Before you can start, some tools must be installed first, so everything can go on smoothly. Since connaisseur is an addition to Kubernetes, a cluster is obviously needed. You can use any kind of Kubernetes service from different providers, such as *Azure* or *AWS*, but for the sake of this guide, a local [*minikube*](https://kubernetes.io/docs/tasks/tools/install-minikube/) (with virtualbox as driver!) instance is being used. For accessing the cluster you'll also need the [*Kubernetes command-line tool*](https://kubernetes.io/docs/tasks/tools/install-kubectl/) and the installation of new services/tools into Kubernetes is done with [*helm3*](https://helm.sh/docs/intro/install/).

For building and signing container images, [*docker*](https://docs.docker.com/engine/install/) will be needed.

Finally you'll need *git* for cloning repositories used in this guide.

```bash
sudo apt-get install git
```

### Installing Harbor

When signing docker images, you need two things. First, an image registry that stores the images and second, a notary server, that stores the signature information. Conveniently there is a service called *harbor*, that combines the two in a nice bundle, including additional functionalities such as container vulnerability scanning. We suggest you using this, as it makes the setup a lot easier.

> Alternatively, should you already have an image registry and don't want to switch to harbor, you can install notary separately using their [github repo](https://github.com/theupdateframework/notary). The notary server needs to be connected to the same authentication server, that your registry is using (if present) and only supports token authentication. It's not advised to use an unauthenticated notary server. For the rest of this setup guide, it is assumed, that harbor is in use.

Now clone the *harbor-helm* repository, that holds all necessary resources for installing harbor.

```bash
git clone https://github.com/goharbor/harbor-helm.git
```

In the cloned repository you can find a `values.yaml` file, in which you can make some configurations, but for this guide keep things as is. You should create a new namespace for the harbor instance and then install it via helm (`cd` into the repository first).

> The harbor installation uses an _ingress_ to redirect all requests to the relevant components. So make sure an ingress controller is installed in the cluster. For minikube just check with `minikube addons list` and enable it with `minikube addons enable ingress`.

```bash
kubectl create namespace harbor
kubectl config set-context --current --namespace harbor
helm install harbor .
```

After a few minutes harbor should be running on your cluster. You can check whether all Pods/Depolyments are running with `kubectl -n harbor get all`.

#### (Optional) Installing Certificates

A little inconvenience about this simple setup is, that it is using self-signed certificates, that will hinder further steps from successfully executing. So let's install the self-signed certificates to get the real certificate experience.

First retrieve the certificate from the Kubernetes secrets and store it somewhere locally.

```bash
kubectl -n harbor get secrets harbor-harbor-ingress -o jsonpath="{.data['ca\.crt']}" | base64 -d > harbor-ca.crt
```

Second install the certificate, both locally and in the cluster. For the local installation, create the two directories `/etc/docker/certs.d/core.harbor.domain` and `~/.docker/tls/notary.harbor.domain` and copy the certificate in there.

```bash
mkdir -p /etc/docker/certs.d/core.harbor.domain
mkdir -p ~/.docker/tls/notary.harbor.domain

cp harbor-ca.crt /etc/docker/certs.d/core.harbor.domain
cp harbor-ca.crt ~/.docker/tls/notary.harbor.domain
```

For installing the certificate into the cluster (minikube), things get a bit more complicated. Copy the certificate into your cluster using `scp`.

```bash
scp -i $(minikube ssh-key) harbor-ca.crt docker@$(minikube ip):~/harbor-ca.crt
```

Then ssh into your cluster and switch to root user.

```bash
$ minikube ssh
                         _             _
            _         _ ( )           ( )
  ___ ___  (_)  ___  (_)| |/')  _   _ | |_      __  
/' _ ` _ `\| |/' _ `\| || , <  ( ) ( )| '_`\  /'__`\
| ( ) ( ) || || ( ) || || |\`\ | (_) || |_) )(  ___/
(_) (_) (_)(_)(_) (_)(_)(_) (_)`\___/'(_,__/'`\____)

$ sudo -s
$
```

Then create the `/etc/docker/certs.d/core.harbor.domain` directory and copy the certificate in there.

```bash
mkdir -p /etc/docker/certs.d/core.harbor.domain
cp harbor-ca.crt /etc/docker/certs.d/core.harbor.domain
```

After that, exit minikube (enter `exit` twice).

Lastly edit your local `/etc/hosts` file and add harbor's and notary's domain names in there with the IP address of your minikube cluster. That way you can access harbor via it's domain name and don't get into trouble with the certificate.

```bash
sudo echo "\n$(minikube ip)\t\tcore.harbor.domain\n$(minikube ip)\t\tnotary.harbor.domain" >> /etc/hosts
```

### Signing images

#### Connect to registry

Now with harbor installed and it's domain name added to the `/etc/hosts` file, you can access it via `core.harbor.domain` in your web browser. Unfortunately your browser won't accept the self-signed certificate, so you have to manually approve the connection. Click "More Information" (or something similar to this; this is different on each web browser) and then "Yes, I really want to visit this super insecure website". This should bring you to the harbor login screen. The default credentials are 'admin' and 'Harbor12345' – enter them! Congrats, your are now at the harbor main page.

![Harbor Overview](img/harbor-overview.png)

Here you are going to create a new user, so you don't have to use the admin credentials for everything. Go to "Administration -> Users" and click "+ New User". Think of a cool name and password; we'll be using 'test' and 'Omegasecure8'. Then create a new project in the "Projects" tab, called 'sample'. Click on the newly created project and add your new user to the members list, as an "Developer".

Ok cool! Now let's login into the harbor image registry, by using the credentials of the 'test'-user.

```bash
docker login --username="test" --password="Omegasecure8" core.harbor.domain
```

Similar things have to be done for the cluster, so it can pull images from he registry. So create an image pull secret.

> You probably want to change namespaces, so you don't create everything in the harbor namespace. Use `kubectl config set-context --current --namespace default` to switch to the default namespace.

```bash
kubectl create secret docker-registry regcred --docker-server=core.harbor.domain --docker-username=test --docker-password=Omegasecure8
```

#### Build unsigned image

To better see the difference between signed and non-signed image, you'll first create a normal non-signed image and push it into the registry. Use this simple _python_ web server as your application code.

```python
from flask import Flask

app = Flask(__name__)


@app.route('/')
def hello_world():
    return 'Hello World! This is a normal docker image!'


if __name__ == '__main__':
    app.run(host='0.0.0.0')
```

Store this in `app.py` and build a docker image out of it, using the following `Dockerfile`.

```bash
FROM python:3.7-alpine
WORKDIR /app
RUN pip install Flask
COPY app.py /app
ENTRYPOINT [ "python" ]
CMD [ "app.py" ]
```

Build the image and push it into the registry.

> The image needs to be tagged as \<registry\>/\<repo>/\<image-name\>, whereas the _registry_ is the domain name of the image registry (`core.harbor.domain`), the _repo_ being the newly created project (`sample`) and _image-name_ an arbitrary name.

```bash
docker build -t core.harbor.domain/sample/unsigned-image .
docker push core.harbor.domain/sample/unsigned-image
```

Now the image should reside in the registry. You can check that, by using the harbor web interface and you can start up a service in your cluster, using this very image.

```bash
kubectl create -f - << EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: sample-deployment
  labels:
    app: sample
spec:
  selector:
    matchLabels:
      app: sample
  replicas: 1
  template:
    metadata:
      labels:
        app: sample
    spec:
      containers:
      - name: sample
        image: core.harbor.domain/sample/unsigned-image
        imagePullPolicy: Always
        ports:
        - containerPort: 5000
      imagePullSecrets:
        - name: regcred
---
apiVersion: v1
kind: Service
metadata:
  name: sample
  labels:
    app: sample
spec:
  ports:
  - name: port
    port: 8080
    targetPort: 5000
  selector:
    app: sample
  type: LoadBalancer
EOF
```

The command `minikube service list -n default` should now provide you with an URL, behind which you'll find your python web server.

#### Build signed image

Phew. Still there? Now starts the exciting part, the image signing. So change up the application code a bit, to better differentiate the signed and unsigned version. You can use the same code from above, just modify the `hello_world` method a bit.

```python
def hello_world():
    return 'Hello World! This is a signed docker image!'
```

Now build the new image, but don't push it to the registry yet! Also chose a new name for the image and give it a tag, since only images with tags can be signed.

```bash
docker build -t core.harbor.domain/sample/signed-image:v1 .
```

Before you can push the image to the registry, you'll have to activate _Docker Content Trust_, which will sign the image for you, once you push it. Activate it, by setting the `DOCKER_CONTENT_TRUST` environment variable to `1` and set `DOCKER_CONTENT_TRUST_SERVER` to your notary instance.

```bash
export DOCKER_CONTENT_TRUST=1
export DOCKER_CONTENT_TRUST_SERVER=https://notary.harbor.domain
```

> The reason why this is done after the image has been built, is because once Docker Content Trust is active, the docker client will only pull in images that are signed, based on the signing data from the notary server. The built image uses `python:3.7-alpine` as basis, that needs to be pulled in and the harbor notary instance is completely empty, thus has no signing data. The building process would therefore fail, if activated beforehand.

Now you can push the image, which will sign it at the same time.

```bash
docker image push core.harbor.domain/sample/signed-image:v1
```

Since the notary instance inside harbor is completely empty, it will ask you to setup a passphrase for a `root` and `targets` key. These keys are being generated for you and are used to create the image signature. The `root` key is the source of all trust and is needed whenever you are trying to sign a new image repository. The `targets` key will be need for all changes within a repository. Both private parts of the keys are stored on your machine, in the `~/.docker/trust/private` directory, encrypted with your passphrases. The public parts reside in the notary server.

That's it. You got yourself a signed image. Check again in the web interface, by navigating to your 'sample' project, to 'Repositories' -> 'sample/signed-image' -> 'v1', where you should get an overview of the image. There should be an indicator, whether the image is signed or not.

![Signed image indicator](img/signed_example.png)

Same as before, you can start up the image in your cluster using the same example as given above, but make sure you change the image reference and name of the deployment as well as the service (`metadata` -> `name`).

### Installing connaisseur

> Before installing connaisseur, you may want to clean up the testing services of your two images. Just run `kubectl delete all -lapp=sample`

It is time – **connaisseur**. Clone the repository to an appropriate location and `cd` into it.

```bash
git clone git@gitlab.com:sse-secure-systems/connaisseur.git
cd connaisseur
```

In there is a `helm` directory, which holds a `values.yaml` file, that needs to be configured. Change the `notary` section with the appropriate values. In `notary.selfsignedCert` you have to put in the certificate from `harbor-ca.crt`.

```yaml
notary:
  host: notary.harbor.domain
  selfsigned: true
  selfsignedCert: |
    -----BEGIN CERTIFICATE-----
    -----END CERTIFICATE-----
  auth:
    enabled: true
    user: test
    password: Omegasecure8
  rootPubKey: |
    -----BEGIN PUBLIC KEY-----
    -----END PUBLIC KEY-----
```

For the `notary.rootPubKey` field, you'll need the public part of the notary's `root` key. It's private component resides in your `~/.docker/trust/private` directory. With `openssl` you can get the public part form it, but have to enter the passphrase you set, when generating it. Copy the contents of the public key into the `notary.rootPubKey` field of the `helm/values.yaml`.

```bash
cd ~/.docker/trust/private
sed '/^role:\sroot$/d' $(grep -iRl "role: root" .) > root-priv.key
openssl ec -in root-priv.key -pubout -out root-pub.pem
cd -
```

And with that, everything is ready to install connaisseur. You can use the Makefile in the `connaisseur` repository.

```bash
$ make install
bash helm/certs/gen_certs.sh
Generating RSA private key, 4096 bit long modulus (2 primes)
.............................++++
.................................................................++++
e is 65537 (0x010001)
Generating RSA private key, 4096 bit long modulus (2 primes)
..++++
.....++++
e is 65537 (0x010001)
Signature ok
subject=CN = connaisseur-svc.connaisseur.svc
Getting CA Private Key
kubectl create ns connaisseur || true
namespace/connaisseur created
kubectl config set-context --current --namespace connaisseur
Context "minikube" modified.
helm install connaisseur helm --wait
NAME: connaisseur
LAST DEPLOYED: Fri May 29 15:30:52 2020
NAMESPACE: connaisseur
STATUS: deployed
REVISION: 1
TEST SUITE: None
```

When this is done, connaisseur should be up and running in the `connaisseur` namespace. Check with `kubectl get all -n connaisseur`.

```bash
$ kubectl get all -n connaisseur
NAME                                          READY   STATUS    RESTARTS   AGE
pod/connaisseur-deployment-6d579b4946-w98fw   1/1     Running   0          18s

NAME                      TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)   AGE
service/connaisseur-svc   ClusterIP   10.111.126.76   <none>        443/TCP   18s

NAME                                     READY   UP-TO-DATE   AVAILABLE   AGE
deployment.apps/connaisseur-deployment   1/1     1            1           18s

NAME                                                DESIRED   CURRENT   READY   AGE
replicaset.apps/connaisseur-deployment-6d579b4946   1         1         1       18s
```

Now switching back to the default namespace (`kubectl config set-context --current --namespace default`), try applying the two images you built form before. First the unsigned one. Applying it should give the following error.

```bash
service/sample created
Error from server: error when creating "STDIN": admission webhook "connaisseur-svc.connaisseur.svc" denied the request: no trust data for image "core.harbor.domain/sample/unsigned-image:latest".
```

As expected, connaisseur blocks the creation of the deployment, since the used image isn't signed. Success!

> Note that the service still gets created, as it has no image reference and is considered harmless for connaisseur.

Now with the signed version, everything should work just fine, as it has a signature. Go apply it.

```bash
$ kubectl create -f - << EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: sample-deployment
  labels:
    app: sample
spec:
  selector:
    matchLabels:
      app: sample
  replicas: 1
  template:
    metadata:
      labels:
        app: sample
    spec:
      containers:
      - name: sample
        image: core.harbor.domain/sample/signed-image:v1
        imagePullPolicy: Always
        ports:
        - containerPort: 5000
      imagePullSecrets:
        - name: regcred
---
apiVersion: v1
kind: Service
metadata:
  name: sample
  labels:
    app: sample
spec:
  ports:
  - name: port
    port: 8080
    targetPort: 5000
  selector:
    app: sample
  type: LoadBalancer
EOF

deployment.apps/sample-deployment created
service/sample created
```

There you go. Now your cluster is protected from any attacker, that got `kubectl` access and wants to deploy random images. It also protects from attackers sitting inside you registry, who are redirecting image tags with their corresponding digests. So don't worry about bitcoin miners anymore, unless there are signed of course!

Cheers.
