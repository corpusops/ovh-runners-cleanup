FROM corpusops/python:3
ENV PYTHONPATH=/setup/cleanupcron
ENV MACHINE_VER=0.16.1
RUN apt update -qq
RUN bash -euxc '\
	base="https://github.com/docker/machine/releases/download/v$MACHINE_VER" \
  && curl -L $base/docker-machine-$(uname -s)-$(uname -m) >/tmp/docker-machine \
  && install /tmp/docker-machine /usr/local/bin/docker-machine'
ADD req* *.py /app/
WORKDIR /app
RUN pip install -U -r req*txt
CMD python app.py
