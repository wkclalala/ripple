import argparse
import boto3
import json
import util


def statistics(bucket_name, token, prefix, params, show=False):
  s3 = boto3.resource("s3")
  bucket = s3.Bucket(bucket_name)
  memory_parameters = json.loads(open("json/memory.json").read())
  if prefix is None and token is None:
    objects = list(bucket.objects.all())
  elif prefix is None and token is not None:
    objects = list(bucket.objects.all())
    objects = list(filter(lambda o: token == o.key.split("/")[1], objects))
  elif prefix is not None and token is None:
    objects = list(bucket.objects.filter(Prefix=str(prefix)))
  else:
    objects = list(bucket.objects.filter(Prefix=str(prefix) + "/" + token))

  objects.sort(key=lambda obj: obj.key)
  messages = []
  costs = {-1: 0}
  for objSum in objects:
    obj_format = util.parse_file_name(objSum.key)
    obj = s3.Object(bucket_name, objSum.key)
    body = json.loads(obj.get()["Body"].read().decode("utf-8"))
    duration = body["duration"]

    for prefix in [-1, obj_format["prefix"]]:
      if prefix not in costs:
        costs[prefix] = 0
      costs[prefix] += (body["write_count"] + body["list_count"]) / 1000.0 * 0.005
      costs[prefix] += body["read_count"] / 1000.0 * 0.0004
      memory_size = str(params["functions"][body["name"]]["memory_size"])
      costs[prefix] += memory_parameters["lambda"][memory_size] * int((duration + 99) / 100)

    if show:
      print(obj)
      print(body)
      print("")
    messages.append({"key": objSum.key, "body": body})

  for prefix in costs.keys():
    if prefix != -1:
      print(prefix, costs[prefix])

  print("Total Cost", costs[-1])
  return [costs, messages]


def main():
  parser = argparse.ArgumentParser()
  parser.add_argument("--bucket_name", type=str, required=True, help="Bucket to clear")
  parser.add_argument("--token", type=str, default=None, help="Only delete objects with the specified timestamp / nonce pair")
  parser.add_argument("--prefix", type=int, default=None, help="Only delete objects with the specified prefix")
  parser.add_argument("--parameters", type=str, help="JSON file containing application setup")
  args = parser.parse_args()
  params = json.loads(open(args.parameters).read())
  statistics(args.bucket_name, args.token, args.prefix, params, show=True)


if __name__ == "__main__":
  main()
