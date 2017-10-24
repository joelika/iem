"""Hey, we are going to QC precipitation, somehow!

Implementation Thoughts:

1. We are really only caring about the situation of having too low of precip
2. We'll take the stage IV product as gospel
3. We won't update the 'raw' precip tables
4. This uses the flag 'E' for estimated

"""
from __future__ import print_function
import datetime
import json
import sys

import pytz
import psycopg2
import requests
import pandas as pd
from pandas.io.sql import read_sql
from pyiem.network import Table as NetworkTable
from pyiem.datatypes import distance


def print_debugging(station):
    """Add some more details to the output messages to help with ticket res"""
    pgconn = psycopg2.connect(database='isuag', host='iemdb')
    cursor = pgconn.cursor()
    cursor.execute("""
    SELECT valid, rain_mm_tot / 25.4, rain_mm_tot_qc / 25.4 from sm_daily
    WHERE station = %s and (rain_mm_tot > 0 or rain_mm_tot_qc > 0)
    ORDER by valid DESC LIMIT 10
    """, (station, ))
    print("     Date           Obs     QC")
    for row in cursor:
        print("     %s   %5.2f  %5.2f" % row)


def get_hdf(nt, date):
    """Fetch the hourly dataframe for this network"""
    # Get our stage IV hourly totals
    rows = []
    for station in nt.sts:
        # service provides UTC dates, so we need to request two days
        for ldate in [date, date + datetime.timedelta(days=1)]:
            uri = ("http://iem.local/json/stage4/%.2f/%.2f/%s"
                   ) % (nt.sts[station]['lon'],
                        nt.sts[station]['lat'], ldate.strftime("%Y-%m-%d"))
            res = requests.get(uri)
            j = json.loads(res.content)
            for entry in j['data']:
                rows.append(dict(station=station,
                                 valid=datetime.datetime.strptime(
                                     entry['end_valid'],
                                     '%Y-%m-%dT%H:%M:%SZ').replace(
                                         tzinfo=pytz.utc),
                                 precip_in=entry['precip_in']))
    df = pd.DataFrame(rows)
    df.fillna(0, inplace=True)
    return df


def update_precip(date, station, hdf):
    """Do the update work"""
    sts = datetime.datetime(date.year, date.month, date.day, 7)
    sts = sts.replace(tzinfo=pytz.utc)
    ets = sts + datetime.timedelta(hours=24)
    ldf = hdf[(hdf['station'] == station) &
              (hdf['valid'] >= sts) &
              (hdf['valid'] < ets)]

    newpday = distance(ldf['precip_in'].sum(), 'IN')
    # update iemaccess
    pgconn = psycopg2.connect(database='iem', host='iemdb')
    cursor = pgconn.cursor()
    cursor.execute("""
    UPDATE summary s
    SET pday = %s
    FROM stations t
    WHERE t.iemid = s.iemid and s.day = %s and t.id = %s and
    t.network = 'ISUSM'
    """, (newpday.value('IN'), date, station))
    cursor.close()
    pgconn.commit()
    # update isusm
    pgconn = psycopg2.connect(database='isuag', host='iemdb')
    cursor = pgconn.cursor()
    # daily
    cursor.execute("""
    UPDATE sm_daily
    SET rain_mm_tot_qc = %s, rain_mm_tot_f = 'E'
    WHERE valid = %s and station = %s
    """, (newpday.value('MM'), date, station))
    for _, row in ldf.iterrows():
        # hourly
        total = distance(row['precip_in'], 'IN').value('MM')
        cursor.execute("""
        UPDATE sm_hourly
        SET rain_mm_tot_qc = %s, rain_mm_tot_f = 'E'
        WHERE valid = %s and station = %s
        """, (total, row['valid'], station))
        # 15minute
        for minute in [45, 30, 15, 0]:
            cursor.execute("""
            UPDATE sm_15minute
            SET rain_mm_tot_qc = %s, rain_mm_tot_f = 'E'
            WHERE valid = %s and station = %s
            """, (total / 4.,
                  row['valid'] - datetime.timedelta(minutes=minute), station))
    cursor.close()
    pgconn.commit()


def main(argv):
    """ Go main go """
    date = datetime.date(int(argv[1]), int(argv[2]), int(argv[3]))
    pgconn = psycopg2.connect(database='isuag', host='iemdb')
    nt = NetworkTable("ISUSM")

    # Get our obs
    df = read_sql("""
     SELECT station, rain_mm_tot_qc / 25.4 as obs from sm_daily where
     valid = %s ORDER by station ASC
    """, pgconn, params=(date, ), index_col='station')
    hdf = get_hdf(nt, date)

    # lets try some QC
    for station in df.index.values:
        # the daily total is 12 CST to 12 CST, so that is always 6z
        # so we want the 7z total
        sts = datetime.datetime(date.year, date.month, date.day, 7)
        sts = sts.replace(tzinfo=pytz.utc)
        ets = sts + datetime.timedelta(hours=24)
        # OK, get our data
        ldf = hdf[(hdf['station'] == station) &
                  (hdf['valid'] >= sts) &
                  (hdf['valid'] < ets)]
        df.at[station, 'stage4'] = ldf['precip_in'].sum()

    df['diff'] = df['obs'] - df['stage4']
    # We want to QC the case of having too low of precip, how low is too low?
    # if stageIV > 0.1 and obs < 0.05
    df2 = df[(df['stage4'] > 0.1) & (df['obs'] < 0.05)]
    for station, row in df2.iterrows():
        print(("ISUSM fix_precip %s %s stageIV: %.2f obs: %.2f"
               ) % (date, station, row['stage4'], row['obs']))
        print_debugging(station)
        update_precip(date, station, hdf)


if __name__ == '__main__':
    main(sys.argv)
