# k6 Docker example

The governed runtime source is [`docker/Dockerfile`](../../docker/Dockerfile).

Build it:

```bash
docker build -t qa-k6-runtime -f docker/Dockerfile .
```

Safe default startup:

```bash
docker run --rm qa-k6-runtime
```

Starting the image without an explicit scenario runs `k6 version`; it does not generate target traffic.

To run repository tests, mount the repository and provide only the environment variables required by the selected profile. Sustained profiles still enforce the same runtime authorization contract even when `k6 run` is invoked inside Docker.
