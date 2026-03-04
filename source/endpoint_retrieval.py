import yaml
from pathlib import Path

def get_service_host_port(benchmark_name: str):
    """
    Reads docker-compose.yml and returns all public entrypoints
    based solely on the 'ports:' section.

    Returns:
        List of URLs like ["http://localhost:80", "http://localhost:5000"]
    """
    BASE_DIR = Path(__file__).parent.parent
    compose_file = BASE_DIR / f"X-BOW/benchmarks/{benchmark_name}/docker-compose.yml"

    if not compose_file.exists():
        raise RuntimeError(f"docker-compose.yml not found for benchmark {benchmark_name}")

    # Load docker-compose.yml
    with open(compose_file, "r") as f:
        compose_data = yaml.safe_load(f)

    services = compose_data.get("services", {})

    entrypoints = []

    for service_name, service_data in services.items():
        ports = service_data.get("ports", [])
        for port in ports:
            port_str = str(port)

            # "80:80"
            if ":" in port_str:
                host_port = port_str.split(":")[0]
                entrypoints.append(f"http://localhost:{host_port}")

            # "5000" (rare, but possible)
            else:
                entrypoints.append(f"http://localhost:{port_str}")

    return entrypoints



# Example usage
if __name__ == "__main__":
    endpoint = get_service_host_port("XBEN-010-24")
    print(f"Access the service at: {endpoint}")
