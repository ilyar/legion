FROM python:3.6-alpine

RUN apk add -U \
      gcc \
      linux-headers \
      musl-dev \
    && \
    pip install \
      uwsgi==2.0.18 \
      Flask==1.0.2 \
      MarkupSafe==1.1.0 \
      Werkzeug==0.14.1 \
      click==7.0 \
      itsdangerous==1.1.0 \
    && \
    apk del \
      gcc \
      linux-headers \
      musl-dev

EXPOSE 80

CMD /usr/local/bin/uwsgi --http :80 --wsgi-file /controller.py

COPY controller.py /
