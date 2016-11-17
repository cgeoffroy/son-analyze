FROM jupyter/base-notebook

### Warning: this Dockerfile's context is the root directory of the project

USER root

RUN conda install -y nomkl git pyyaml pandas \
    # Install common packages, Ansible and Git
    && echo 'Done'

WORKDIR /son-analyze

COPY requirements.txt /son-analyze/
COPY son-scikit/requirements.txt /son-analyze/son-scikit/

RUN cd /son-analyze \
    && pip install -r requirements.txt \
    && cd son-scikit \
    && sed -i 's/^son-analyze/# son-analyze/g' requirements.txt \
    && pip install -r requirements.txt \
    && echo 'Done'

COPY . /son-analyze

RUN cd /son-analyze \
    && ./scripts/clean.sh \
    && pip install -r requirements.txt \
    && echo 'Local install' \
    && python3.5 setup.py develop \
    && cd son-scikit \
    && pip install -r requirements.txt \
    && python3.5 setup.py develop \
    && echo 'Done'

RUN sed -i '5 a cp /son-analyze/son-scikit/src/son_scikit/resources/Welcome.ipynb /home/jovyan/work/' /usr/local/bin/start-notebook.sh \
    && sed -i '6 a cp /son-analyze/son-scikit/src/son_scikit/resources/helpers.py /home/jovyan/work/' /usr/local/bin/start-notebook.sh

WORKDIR /home/jovyan/work

USER jovyan
