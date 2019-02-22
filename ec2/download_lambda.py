import argparse
import boto3
import graph
import inspect
import json
import os
import sys
currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parentdir = os.path.dirname(currentdir)
sys.path.insert(0, parentdir)
import statistics


def download(subfolder, param_file):
  s3 = boto3.resource("s3")
  bucket = s3.Bucket("maccoss-log")
  objSums = bucket.objects.filter(Prefix="1/")
  params = json.loads(open(param_file).read())

  total_cost = 0.0
  for objSum in objSums:
    token = objSum.key.split("/")[1]
    file_name = subfolder + "/" + token
    if not os.path.isfile(file_name):
      [stats, costs, durations] = statistics.statistics("maccoss-log", objSum.key.split("/")[1], None,  params, None)
      total_cost += costs[-1]

      with open(file_name, "w+") as f:
        f.write(json.dumps({"cost": costs, "durations": durations, "stats": stats}))

def s3_cost(stats):
  cost = 0
  list_count = 0
  read_count = 0
  write_count = 0
  for message in stats["messages"]:
    list_count += message["list_count"]
    read_count += message["read_count"]
    write_count += message["write_count"]

  cost += (write_count + list_count) / 1000.0 * 0.005
  cost += read_count / 1000.0 * 0.0004
  return cost

def process(subfolder):
  lambda_ranges = []
  task_ranges = []
  total_cost = 0.0
  average_duration = 0.0
  count = 0
  list_count = 0
  read_count = 0
  write_count = 0
  for file in os.listdir(subfolder):
    name = subfolder + "/" + file
    if name.endswith(".png") or name.endswith("README"):
      continue
    results = json.loads(open(name).read())
    for stage in results["stats"]:
      for message in stage["messages"]:
        start_time = message["start_time"]
        end_time = start_time + message["duration"] / 1000.0
        lambda_ranges.append([start_time, 1])
        lambda_ranges.append([end_time, -1])
        list_count += message["list_count"]
        read_count += message["read_count"]
        write_count += message["write_count"]

    durations = results["durations"]
    total_cost += results["cost"]["-1"]
    d = durations["-1"][1] - durations["-1"][0]
    print("duration", d)
    average_duration += d
    task_ranges.append([durations["-1"][0], 1])
    count += 1
    task_ranges.append([durations["-1"][1], -1])

  total_s3_cost = 0
  total_s3_cost += (write_count + list_count) / 1000.0 * 0.005
  total_s3_cost += read_count / 1000.0 * 0.0004
  start_time = min(list(map(lambda t: t[0], task_ranges)))
  ranges = [lambda_ranges, task_ranges]
  results = list(map(lambda r: [], ranges))
  for i in range(len(ranges)):
    ranges[i] = sorted(ranges[i], key=lambda r: r[0])
    ranges[i] = list(map(lambda r: [r[0] - start_time, r[1]], ranges[i]))
    num = 0
    for j in range(len(ranges[i])):
      [timestamp, increment] = ranges[i][j]
      results[i].append([timestamp - 1, num])
      num += increment
      results[i].append([timestamp, num])

  average_duration /= count
  average_cost = total_cost / count
  print("Total S3 cost", total_s3_cost)
  print("Total cost", total_cost)
  print("Average cost", average_cost)
  print("Average duration", average_duration)
  return results


def main():
  parser = argparse.ArgumentParser()
  parser.add_argument("--subfolder", type=str, required=True, help="Subfolder to download results in")
  parser.add_argument("--parameters", type=str, required=True, help="Location of JSON parameter file")
  parser.add_argument("--start_range", type=int, help="Start timestamp of zoom region")
  parser.add_argument("--end_range", type=int, help="End timestamp of zoom region")
  args = parser.parse_args()
  download(args.subfolder, args.parameters)
  numbers = process(args.subfolder)
  colors = ["red", "blue"]
  labels = ["Number of Lambdas", "Number of Running Jobs"]
  graph.graph(args.subfolder, numbers, colors, labels, args.start_range, args.end_range)

if __name__ == "__main__":
  main()
