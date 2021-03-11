#!/usr/bin/env python
"""Extract events from kafka and write them to hdfs
"""
import json
from pyspark.sql import SparkSession
from pyspark.sql.functions import udf, from_json
from pyspark.sql.types import StructType, StructField, StringType, DoubleType, IntegerType


def event_schema():
    return StructType([
        StructField("accept", StringType(), True),
        StructField("host", StringType(), True),
        StructField("user_agent", StringType(), True),
        StructField("timestamp", StringType(), True),
        StructField("event_type", StringType(), True),
        StructField("user_id", StringType(), True),
        StructField("status", StringType(), True),
        StructField("org", StringType(), True),
        StructField("level", StringType(), True),
        StructField("cost", DoubleType(), True),        
        StructField("player_created", StringType(), True),
        StructField("player_wealth", DoubleType(), True),
        StructField("player_num_affiliations", IntegerType(), True),
    ])

@udf('boolean')
def is_event_of_interest(event_as_json):
    """udf for filtering events
    """
    event = json.loads(event_as_json)
    if 'join' in event['event_type']:
        return True
    return False

def main():
    """main
    """
    spark = SparkSession \
        .builder \
        .appName("ExtractSocialEventsJob") \
        .enableHiveSupport() \
        .getOrCreate()

    raw_events = spark \
        .readStream \
        .format("kafka") \
        .option("kafka.bootstrap.servers", "kafka:29092") \
        .option("subscribe", "placebo_all_events") \
        .load()

    sub_events = raw_events \
        .filter(is_event_of_interest(raw_events.value.cast('string'))) \
        .select(raw_events.value.cast('string').alias('raw_event'),
                raw_events.timestamp.cast('string').alias('spk_ts'),
                from_json(raw_events.value.cast('string'),
                          event_schema()).alias('json')) \
        .select('raw_event', 'spk_ts', 'json.*')

    sink = sub_events \
        .writeStream \
        .format("parquet") \
        .option("mode", "overwrite") \
        .option("checkpointLocation", "/tmp/checkpoints_for_social") \
        .option("path", "/tmp/social") \
        .trigger(processingTime="5 seconds") \
        .start()

    sink.awaitTermination()

if __name__ == "__main__":
    main()
