import subprocess
import asyncio
import sys

async def do_subprocess(node):
    proc = await asyncio.create_subprocess_exec("vagrant", "provision", node, stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr)
    returncode = await proc.wait()
    print(f'Return code = {returncode}')

nodes = [ 'node0' + str(i) for i in range(1, 3 + 1) ]
nodes.append('storage')

subprocess.run('vagrant up --no-provision', stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr)

futures = [asyncio.ensure_future(do_subprocess(node)) for node in nodes]

loop = asyncio.get_event_loop()
loop.run_until_complete(asyncio.gather(*futures))
loop.close()
