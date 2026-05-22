import argparse
import sys
from pathlib import Path

try:
    from prt_mcp_common.transport import add_transport_args, run_server
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "PrtMcpCommon" / "src"))
    from prt_mcp_common.transport import add_transport_args, run_server

from .server import create_server, readiness_check


def main() -> None:
    parser = argparse.ArgumentParser(description="ProRata OpenSearch MCP server")
    add_transport_args(parser)
    args = parser.parse_args()
    run_server(create_server(), args, readiness_check=readiness_check)


if __name__ == "__main__":
    main()
