FROM python:3.5-alpine3.9

RUN apk --update add ttf-dejavu graphviz

RUN    pip install --upgrade pip \
    && pip install \
              sphinx==1.8.0 \
              sphinx_rtd_theme==0.4.1 \
              sphinx-autobuild==0.7.1 \
              recommonmark==0.5.0 \
              sphinx-markdown-tables==0.0.9 \
              rinohtype==0.3.1


ADD containers/docs-builder/generate.sh /
RUN chmod +x /generate.sh