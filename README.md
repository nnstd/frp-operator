# frp-operator

An operator for managing [frp](https://github.com/fatedier/frp) instances (frps, frpc) and
frpc endpoints.

## deploy

`kubectl apply -f https://raw.githubusercontent.com/nnstd/frp-operator/master/deploy.yaml`

## examples

### frp server

```yaml
apiVersion: frp.nonamestudio.me/v1
kind: FRPServer
metadata:
  name: demo
spec:
  plugins: []
  ports:
    kcp: 0
    tcp: 7000
    udp: 0
  prometheus: true
  service:
    type: LoadBalancer
  token:
    secret: frps-home-token # created automatically
```

### frp client

```yaml
kind: Secret
apiVersion: v1
metadata:
  name: frpc-frp-token
stringData:
  token: your-frp-token
type: Opaque
---
apiVersion: v1
kind: Secret
metadata:
  name: frpc-dashboard-creds
stringData:
  password: admin
  username: admin
type: Opaque
---
apiVersion: frp.nonamestudio.me/v1
kind: FRPClient
metadata:
  name: some-frp
spec:
  dashboard:
    credentials: frpc-dashboard-creds
    port: 7400
    service:
      annotations: {}
      labels: {}
      type: ClusterIP
  namespaceSelector: {}
  selector: {}
  target:
    host: 192.168.0.1
    port: 7000
    token:
      secret: frpc-frp-token
```

### frp client endpoint

#### http

```yaml
apiVersion: frp.nonamestudio.me/v1
kind: FRPClientEndpoint
metadata:
  name: some-service
spec:
  additionalConfig: ''
  compression: true
  encryption: true
  http:
    customDomains:
      - something.example.com
    headers: {}
  local:
    host: some-service.default # can be any dns record or ip
    port: 80
  type: http
```

#### tcp

```yaml
apiVersion: frp.nonamestudio.me/v1
kind: FRPClientEndpoint
metadata:
  name: some-service
spec:
  additionalConfig: ""
  compression: true
  encryption: true
  local:
    host: some-service.default
    port: 25565
  remote:
    port: 25565
  type: tcp
```