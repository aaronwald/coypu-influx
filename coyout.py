#!/usr/bin/env python
import argparse
import asyncio
import logging
import curses
from aioinflux import InfluxDBClient

async def fetchMeasurements(loop, display):
    async with InfluxDBClient(db='testdb', output='iterable') as client:
        resp = await client.query('show measurements', chunked=True, chunk_size=128)
        async for chunk in resp.iterchunks():
            for result in chunk['results']:
                series = result['series']
                for s in series:
                    for measurement in s['values']:
                        display.AddMeasurement(measurement[0])
    try:
        loop.create_task(display.Refresh())
    except Exception as e:
        print(e)

class Display:
    def __init__ (self, loop):
        self.loop = loop

    def __enter__(self):
        self.stdscr = curses.initscr()

        self.measurement_win = self.stdscr.derwin(0, 20, 0, 0)
        self.measurement_win.border()

        self.tag_win = self.stdscr.derwin(0, 20, 0, 20)
        self.tag_win.border()
        
        self.series_win = self.stdscr.derwin(0, 40, 0, 40)
        self.series_win.border()
        
        self.value_win = self.stdscr.derwin(0, 0, 0, 80)
        self.value_win.border()
        
        curses.start_color()
        curses.noecho()
        curses.cbreak()
        curses.curs_set(0)
        self.stdscr.keypad(1)
        self.stdscr.refresh()
        self.stdscr.nodelay(1)

        curses.init_pair(1, curses.COLOR_RED, curses.COLOR_BLACK)
        curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)
        curses.init_pair(3, curses.COLOR_WHITE, curses.COLOR_BLACK)
        self.height, self.width = self.stdscr.getmaxyx()
        self.measurements = []
        return self

    def __exit__(self, *args):
        curses.nocbreak()
        self.stdscr.keypad(0)
        curses.echo()
        curses.endwin()

    def AddMeasurement(self, measurement):
        self.measurements.append(measurement)

    def ListMeasurements(self, win):
        curr_y, curr_x = win.getyx()
        
        # column 0 - measurements
        y = 1
        x = 1
        for m in self.measurements:
            if y == curr_y:
                win.addstr(y,x,m,curses.A_REVERSE)
            else:
                win.addstr(y,x,m)
            y = y+1

        win.refresh()

    async def Refresh(self):
        # column 1 - tag keys
        self.ListMeasurements(self.measurement_win)
        
        # column 2 - tag values
        
        self.stdscr.refresh()
        
    async def get_ch(self):
        while loop.is_running():
            try:
                char = await self.loop.run_in_executor(None, self.stdscr.getch)
            
                curr_y, curr_x = self.stdscr.getyx()
                
                if char == ord('q'):
                    loop.stop()
                elif char == curses.KEY_DOWN:
                    self.stdscr.move(curr_y+1, 0)
                    await self.Refresh()
                elif char == curses.KEY_UP:
                    self.stdscr.move(curr_y-1, 0)
                    await self.Refresh()
                elif char == curses.KEY_LEFT:
                    pass
                elif char == curses.KEY_RIGHT:
                    pass
                elif char == curses.KEY_HOME:
                    pass
                elif char == curses.KEY_RESIZE:
                    self.height,self.width = self.stdscr.getmaxyx()
                    
                    self.measurement_win.clear()
                    self.measurement_win.resize(self.height,20)
                    self.measurement_win.border()
                    
                    self.tag_win.clear()
                    self.tag_win.resize(self.height,20)
                    self.tag_win.border()
                    self.tag_win.refresh()

                    self.series_win.clear()
                    self.series_win.resize(self.height,40)
                    self.series_win.border()
                    self.series_win.refresh()
                
                    self.value_win.clear()
                    self.value_win.resize(self.height,self.width-80)
                    self.value_win.border()
                    self.value_win.refresh()

                    await self.Refresh()
            except Exception as e:
                logging.error(e)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", help="increase output verbosity", action="store_true")
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(format='%(asctime)s %(levelname)s:%(message)s', level=logging.DEBUG)
    else:
        logging.basicConfig(format='%(asctime)s %(levelname)s:%(message)s', level=logging.INFO)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        with Display(loop) as display:
            task1 = loop.create_task(fetchMeasurements(loop, display))
            task2 = loop.create_task(display.get_ch())
            loop.run_forever()
    finally:
        for task in asyncio.Task.all_tasks():
            task.cancel()
            
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()
            
