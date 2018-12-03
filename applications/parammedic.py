import boto3
import re
import subprocess
import util


ITRAQ = re.compile("INFO: iTRAQ: detected")
SILAC = re.compile("INFO: SILAC: detected")
PHOSPHORYLATION = re.compile("INFO: Phosphorylation: detected")
TMT = re.compile(".*INFO:\sTMT:\s([0-9]+)-plex\sreporter\sions\sdetected.*", re.MULTILINE)


def run(file, params, input_format, output_format, offsets):
  s3 = boto3.resource('s3')
  database_bucket = s3.Bucket(params["database_bucket"])

  with open("/tmp/crux", "wb") as f:
    database_bucket.download_fileobj("crux", f)

  subprocess.call("chmod 755 /tmp/crux", shell=True)

  command = "cd /tmp; ./crux param-medic {0:s}".format(file)
  output = subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT).decode("utf-8")
  print(output)

  phos = PHOSPHORYLATION.search(output)
  print("phos", phos)
  itraq = ITRAQ.search(output)
  print("itraq", itraq)
  silac = SILAC.search(output)
  print("silac", silac)
  tmt = TMT.search(output)
  print("tmt", tmt)

  map_bucket = None
  if tmt is not None:
    map_bucket = "maccoss-tmt-fasta"
  elif phos:
    map_bucket = "maccoss-phosphorylation-fasta"
  elif itraq:
    map_bucket = "maccoss-itraq-fasta"
  elif silac:
    map_bucket = "maccoss-silac-fasta"
  else:
    map_bucket = "maccoss-normal-fasta"

  payload = {
    "Records": [{
      "s3": {
        "bucket": {
          "name": params["bucket"],
        },
        "object": {
          "key": util.file_name(input_format),
        },
        "extra_params": {
          "map_bucket": map_bucket,
          "prefix": output_format["prefix"],
        }
      }
    }]
  }

  client = boto3.client("lambda")
  util.invoke(client, params["output_function"], params, payload)

  return []