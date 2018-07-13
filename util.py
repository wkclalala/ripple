import boto3
import constants
import re
import subprocess


def file_name(timestamp, file_id, id, max_id, ext):
  return constants.FILE_FORMAT.format(timestamp, file_id, id, max_id, ext)


def parse_file_name(file_name):
  m = constants.FILE_REGEX.match(file_name)
  timestamp = float(m.group(1))
  file_id = int(m.group(2))
  id = int(m.group(3))
  max_id = int(m.group(4))
  ext = m.group(5)
  return {
    "timestamp": timestamp,
    "file_id": file_id,
    "id": id,
    "max_id": max_id,
    "ext": ext
  }


def get_key_regex(ts, num_bytes):
  regex = constants.FILE_FORMAT.replace("{1:d}", "([0-9]+)").replace("{2:d}", "([0-9]+)")
  regex = regex.replace("{3:d}", "{1:d}").replace("{4:s}", "ms2")
  return re.compile(regex.format(ts, num_bytes))


def clear_tmp():
  subprocess.call("rm -rf /tmp/*", shell=True)


def get_next_spectra(lines, start_index):
  if start_index >= len(lines):
    return (-1, "", -1)

  mass = None

  remaining = "\n".join(lines[start_index:])
  if len(remaining.strip()) == 0:
    return (-1, "", -1)

  split = constants.SPECTRA_START.split(remaining)
  spectra = "S\t" + split[1]

  temp_lines = spectra.strip().split("\n")

  m = list(filter(lambda s: constants.MASS.match(s), temp_lines))
  if len(m) == 0:
    print("ERROR", temp_lines, m)
    return (-1, "", -1)
  assert(len(m) > 0)
  mass = float(constants.MASS.match(m[0]).group(2))

  start_index += len(temp_lines)
  if start_index >= len(lines):
    start_index = -1
  return(mass, spectra, start_index)


def parse_spectra(stream):
  spectra = constants.SPECTRA_START.split(stream)
  spectra = filter(lambda s: len(s) > 0, spectra)
  spectra = list(map(lambda s: "S\t" + s, spectra))

  remainder = spectra[-1]
  spectra = spectra[:-1]
  # Filter out spectra that don't have a mass line
  spectra = list(filter(lambda s: len(list(filter(lambda line: constants.MASS.match(line), s.split("\n")))) > 0, spectra))
  return (spectra, remainder)


def have_all_files(bucket_name, num_bytes, key_regex):
  s3 = boto3.resource("s3")
  bucket = s3.Bucket(bucket_name)

  matching_keys = []
  num_files = None
  for key in bucket.objects.all():
    m = key_regex.match(key.key)
    if m:
      matching_keys.append(key.key)
      if int(m.group(2)) == num_bytes:
        num_files = int(m.group(1))

  return (len(matching_keys) == num_files, matching_keys)


def getMass(spectrum):
  return spectrum[0]


def get_spectra(obj, start_byte, end_byte, num_bytes, remainder):
  if len(remainder.strip()) == 0 and start_byte >= num_bytes:
    return ([], "")

  if start_byte < num_bytes:
    end_byte = min(num_bytes, end_byte)
    stream = obj.get(Range="bytes={0:d}-{1:d}".format(start_byte, end_byte))["Body"].read().decode("utf-8")
  else:
    stream = ""

  stream = remainder + stream
  spectra_regex = list(constants.SPECTRA.finditer(stream))
  spectra_end_byte = spectra_regex[-1].span(0)[1]
  remainder = stream[spectra_end_byte:]

  return (spectra_regex, remainder)