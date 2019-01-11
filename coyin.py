import argparse
import asyncio
from aioinflux import InfluxDBClient
from datetime import datetime

async def main():
    async with InfluxDBClient(db='testdb', output='iterable') as client:

        #await client.create_database(db='testdb')
        for x in range(1,10):
            current_time = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%fZ')

            point = {
                'time': current_time,
                'measurement': 'cpu_load_short',
                'tags': {'host': 'server01',
                         'region': 'us-west'},
                'fields': {'value': 0.64+x}
            }

            await client.write(point)
            await asyncio.sleep(.1)
        resp = await client.query('SELECT value FROM cpu_load_short', chunked=True, chunk_size=128)
        async for chunk in resp.iterchunks():
            yield chunk
            # or await process(chunk)

async def get_docs():
    for x in range(1,10):
        await asyncio.sleep(2)
        yield x

async def fetch():
    async for jdoc in main():
        results = jdoc['results']
        for v in results:
            for s in v['series']:
                names = s['name']
                columns = s['columns']
                values = s['values']
                for v in values:
                    print(names, columns, v)

async def run(cmd):
    proc = await asyncio.create_subprocess_shell(cmd,
                                                 stdout=asyncio.subprocess.PIPE,
                                                 stderr=asyncio.subprocess.PIPE)

    # procs -----------memory---------- ---swap-- -----io---- -system-- ------cpu----- -----timestamp-----
    # r  b   swpd   free   buff  cache   si   so    bi    bo   in   cs us sy id wa st                 UTC
    # 0  0   2048 286872 1318492 14039020    0    0     1     9    2    1  3  1 96  0  0 2019-01-11 23:11:04
    async with InfluxDBClient(db='testdb', output='iterable') as client:
        while True:
            line = await proc.stdout.readline()
            l = line.strip().decode('ascii').split(' ')
            l = list(filter(None, l))
            if len(l) == 19:
                us = float(l[12])
                dayStr = l[17]
                timeStr = l[18]
                
                point = {
                    'time': '%sT%sZ' % (dayStr, timeStr),
                    'measurement': 'cpu_load_short',
                    'fields': {'value': us}
                }
                print(point)
                
                await client.write(point)

                   
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
try:

    loop.create_task(run('vmstat -nt 1'))
#    loop.create_task(run('iostat 1'))
#    loop.run_until_complete(fetch())
    loop.run_forever()
finally:
    loop.run_until_complete(loop.shutdown_asyncgens())
    loop.close()
            
#task = main()
#loop = asyncio.get_event_loop()
#loop.create_task(task)
#loop.run_forever()
#run_until_complete(main())


# proper main
# argaparse read a pid
