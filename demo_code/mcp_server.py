from mcp.server.fastmcp import FastMCP
import sys

server = FastMCP('makaty-server-Demo')

@server.tool(name='add_2_nums')
def add(a, b):
    '''adds 2 numbers'''
    return a + b

if __name__ == '__main__':
    print("MCP Server created successfully :)", file=sys.stderr)
    server.run(transport='stdio')