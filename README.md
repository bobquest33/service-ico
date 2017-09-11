Ico Service
======================

Documentation
-------------

Local development
-----------------
1. Set up a python virtual environment. E.g. with Anaconda:
`conda create -n ico-service python=3.5`  
`source activate ico-service`  
`pip install -r requirements.txt`

If psycopg2 installation fails to install, try `conda install psycopg2==2.6.2`

2. Install `invoke` and related libraries in your virtual environment (you can do this in a separate environment if you prefer):  
`pip install invoke python-dotenv fabric3 pyyaml semver`  

3. Add the project name and details to as well as the virtual environment path to `local.yaml.` For Anaconda, if you don't know the path to your virtual environment, you can run `which python` from within your virtual environment to find your virtual environment path.

4. Use `.local.env.example` as a template to create a `.local.env` with the project environmental variables.

5. To generate a key use `python -c "import string,random; uni=string.ascii_letters+string.digits+string.punctuation; print repr(''.join([random.SystemRandom().choice(uni) for i in range(random.randint(45,50))]))"`

6. Start the postgres database:  
`inv local.compose -c 'up -d postgres'`

7. Check if Docker is running:
`docker ps` or `inv local.compose -c ps`

8. Migrate database:
`inv local.manage migrate`

9. Start the webserver on port 8000:  
`inv local.manage 'runserver --insecure'`

Deployment pre-requisites:
--------------------------
pip install invoke python-dotenv fabric3 pyyaml semver nose
Helm client: https://docs.helm.sh/using_helm/#installing-helm Be sure to install this version: https://github.com/kubernetes/helm/releases/tag/v2.4.2

Kubernetes Setup:
-----------------
Ensure your kubernetes cluster is setup with kube-lego nginx and helm tiller installed.
Note: Install version 2.4.2 of helm: https://github.com/kubernetes/helm/releases/tag/v2.4.2

1. Set up `production.yaml`, `staging.yaml` and `local.yaml`

2. Set up `etc/env/production.env`, `etc/env/staging.env` and `etc/env/local.env`

3. Set up `/etc/k8s/production/values.yaml` and `etc/k8s/staging/values.yaml`

4. Create a drive on Google Cloud for the project's database. e.g.  
`inv k8s.create_volume example-database europe-west1-c 50`

5. Install the kubernetes helm chart:  
`inv k8s.install production`

6. Install redis:
`inv k8s.redis production`

7. Upload secrets to kubernetes: `inv k8s.secrets production`

Deployment:
-----------
1. Commit all changes and tag the release:  
`inv local.git_release`

2. Build the docker image for this release:  
`inv local.docker_release production` or `inv server.docker_release production`

3. Update kubernetes deployment using the version number of the release. E.g.  
`inv k8s.upgrade production 0.0.1` 

Static Files:
-------------
1. Create google cloud bucker:
`inv k8s.create_bucket production`

2. Upload static files:
`inv k8s.upload_static production`

Migrations/ Container commands:
-------------------------------
1. Run migrations:  
`inv k8s.manage production 0.0.1 migrate`

2. Create superuser: There are some issues with the command prompt output when running the command directly, so use this workaround:
Run terminal in new k8s container:
`inv inv k8s.run production 0.0.1 sh -i`
Run the createsuperuser management command:
`python manage.py createsuperuser`
Type `exit` to close and shutdown container.

3. Load Fixtures:
Run terminal in new k8s container:
`inv inv k8s.run production 0.0.1 sh -i`
`python manage.py loaddata data.json`

4. Run interactive django shell:  
`inv k8s.manage production 0.0.1 shell -i`
