# Optional Linux execution worker

The native engagement controller supports `linux_network_scan` through a local Docker Linux daemon. It does not install Docker, pull an image, start Decepticon, or fall back to a remote daemon automatically.

Build explicitly from the reviewed source:

```sh
docker build -t wixal-security-worker:v1 native/worker
```

In Cybersecurity → Engagements, select **Inspect Linux worker**. The adapter requires a local Unix Docker socket and a Linux daemon. Add `linux_network_scan` to a scope revision and review that scope. Each operation also requests explicit review of the immutable image ID, resolved destinations, selected ports and deadline, independently of project bypass.

Each operation creates a dedicated labelled network and container. There are no host mounts, Docker socket mounts, inherited client credentials, arbitrary shell strings or provider fallbacks. The trusted bootstrap applies an nftables default-drop policy allowing only selected destination IPs and TCP ports, obtains a ruleset receipt, then starts unprivileged Nmap through `setpriv` with all child capabilities dropped. DNS is not allowed inside the worker. Only `ports` and `services` profiles and 1–1,024 selected ports are supported. Container memory, process and CPU limits are explicit. Host loopback and link-local destinations are rejected; the adapter does not silently reinterpret target identity.

Cancellation removes only objects whose engagement/run labels match the saved operation. Unknown cleanup is retained as a cleanup requirement. After an interrupted helper, inspect the operation and use **Review worker cleanup**; no scan is replayed automatically. Removing a container does not prove cleanup of target effects.

The Ubuntu base and packages are resolved when built. A local build is not a reproducible or qualified published artifact. The actual image ID is bound to each reviewed invocation and retained with results. Nmap and other image components retain their own licences. No worker image is bundled or published by this change.

Validation on the implementation Mac now includes a dedicated Colima VM (VZ, ARM64, 2 CPU, 2 GiB RAM, 10 GiB disk, no host-directory mounts, no automatic Docker context activation). Source and packaged-helper acceptance both passed actual Linux nftables enforcement, the typed production scan, cancellation and owned container/network removal. The independent firewall check first proved all three owned lab connections reachable, then observed only the allowed destination/port reachable after enforcement. The image's entrypoint hash matched this repository's source. These results qualify the tested ports profile and runtime/image identity; they do not establish arbitrary images, service-probe coverage, exploit capability or multi-tenant security.

A separate Colima runtime can be configured explicitly:

```sh
brew install colima docker
colima start --profile wixal-validation --activate=false --vm-type vz --arch aarch64 --cpu 2 --memory 2 --disk 10 --mount none
docker --host "unix://$HOME/.colima/wixal-validation/docker.sock" build -t wixal-security-worker:v1 native/worker
```

Expand **Optional local Linux runtime** in an engagement brief and supply the absolute path to that profile's `docker.sock`. Review the runtime, then inspect image readiness. The validation VM is stopped after acceptance; restart it explicitly before use. Stop it with `colima stop --profile wixal-validation`. Homebrew tools and the named VM/image remain available for reuse; no login service was enabled.

Reproduce the actual worker acceptance with `native/scripts/worker-acceptance.py --app <development-app> --socket <absolute-local-docker-socket> --output <isolated-directory>`. It creates and removes owned lab services and checks actual network policy. Run only in a dedicated validation environment; it intentionally evaluates outbound allow/deny behaviour.
