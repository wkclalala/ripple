import inspect
import os
import sys
import time
from database import Database, Table, Entry
from typing import Any, BinaryIO, Dict, Iterable, List, Optional, Set, Union

currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parentdir = os.path.dirname(currentdir)
sys.path.insert(0, parentdir)
import database


def equal_lists(list1, list2):
  s1 = set(list1)
  s2 = set(list2)
  return len(s1.intersection(s2)) == len(s1) and len(s2.intersection(s1)) == len(s1)


def create_payload(table_name: str, key: str, prefix: int, file_id: Optional[int]=None, num_files: Optional[int]=None, offsets: Optional[List[int]]=None):
  extra_params: Dict[str, Any] = {"prefix": prefix}
  if file_id:
    extra_params["file_id"] = file_id
    extra_params["num_files"] = num_files

  if offsets:
    extra_params["offsets"] = offsets

  return {
    "Records": [{
      "s3": {
        "bucket": {
          "name": table_name
        },
        "object": {
          "key": key,
        },
        "extra_params": extra_params
      }
    }]
  }


class TestEntry(Entry):
  content: str

  def __init__(self, key: str, content: Optional[Union[str, bytes]], statistics: Optional[database.Statistics]=None):
    self.file_name = key.replace("/tmp/s3/", "")
    self.file_name = key.replace("/tmp/", "")
    self.file_name = self.file_name.replace("/", "-")
    self.file_name = "/tmp/s3/" + self.file_name
    Entry.__init__(self, key, None, None)

    if content is not None:
      if type(content) == str:
        options = "w+"
      else:
        options = "wb+"
      with open(self.file_name, options) as f:
        f.write(content)
      self.length = len(content)
    else:
      self.length = os.path.getsize(self.file_name)
    self.last_modified = time.time()

  def __download__(self, f: BinaryIO) -> int:
    with open(self.file_name, "rb+") as g:
      f.write(g.read())
    return self.length

  def content_length(self) -> int:
    return self.length

  def destroy(self):
    if self.file_name.startswith("/tmp"):
      os.remove(self.file_name)

  def get_content(self) -> str:
    with open(self.file_name) as f:
      return f.read()

  def get_metadata(self) -> Dict[str, str]:
    return {}

  def get_range(self, start_index: int, end_index: int) -> str:
    with open(self.file_name) as f:
      f.seek(start_index)
      return f.read(end_index - start_index + 1)

  def last_modified_at(self) -> float:
    return self.last_modified


class TestTable(Table):
  entries: Dict[str, TestEntry]
  def __init__(self, name: str, statistics: database.Statistics, resources: Any):
    Table.__init__(self, name, statistics, resources)
    self.entries = {}

  def add_entry(self, key: str, content: Union[str, bytes]) -> TestEntry:
    entry = TestEntry(key, content, self.statistics)
    self.entries[key] = entry
    return entry

  def add_entries(self, entries: List[TestEntry]):
    for entry in entries:
      self.entries[entry.key] = entry

  def destroy(self):
    for entry in self.entries.values():
      entry.destroy()


class TestDatabase(Database):
  payloads: List[Dict[str, Any]]
  tables: Dict[str, TestTable]

  def __init__(self):
    Database.__init__(self)
    self.payloads = []
    self.tables = {}
    if not os.path.isdir("/tmp/s3"):
      os.mkdir("/tmp/s3")

  def __del__(self):
    for table in self.tables.values():
      table.destroy()

  def __download__(self, table_name: str, key: str, f: BinaryIO) -> int:
    return self.get_entry(table_name, key).download(f)

  def __get_content__(self, table_name: str, key: str, start_byte: int, end_byte: int) -> str:
    content: str = self.get_object(table_name, key).content
    return content[start_byte:end_byte]

  def __get_entries__(self, table_name: str, prefix: Optional[str]=None) -> List[TestEntry]:
    keys: Iterable[str] = self.tables[table_name].entries.keys()
    if prefix:
      keys = filter(lambda key: key.startswith(prefix), keys)
    entries = list(map(lambda key: self.tables[table_name].entries[key], keys))
    return sorted(entries, key=lambda entry: entry.key)

  def __put__(self, table_name: str, key: str, f: BinaryIO, metadata: Dict[str, str]):
    self.__write__(table_name, key, f.read(), metadata)

  def __read__(self, table_name: str, key: str) -> str:
    return self.get_object(table_name, key).content

  def __write__(self, table_name: str, key: str, content: bytes, metadata: Dict[str, str]):
    self.add_entry(table_name, key, content)
    if not key.endswith(".log"):
      self.payloads.append({
        "Records": [{
          "s3": {
            "bucket": {
              "name": table_name
            },
            "object": {
            "key": key
            }
          }
        }]
      })

  def add_entry(self, table_name: str, key: str, content: bytes):
    self.tables[table_name].add_entry(key, content.decode("utf-8"))

  def add_table(self, table_name: str) -> Table:
    table: Table = TestTable(table_name, self.statistics, None)
    self.tables[table_name] = table
    return table

  def contains(self, table_name: str, key: str) -> bool:
    return table_name in self.tables and key in self.tables[table_name].objects

  def create_table(self, table_name: str) -> TestTable:
    table: TestTable = TestTable(table_name, self.statistics, None)
    self.tables[table_name] = table
    return table

  def get_entry(self, table_name: str, key: str) -> Optional[TestEntry]:
    table: TestTable = self.tables[table_name]
    if key in table.entries:
      return table.entries[key]
    return None

  def invoke(self, client, name, params, payload):
    self.payloads.append(payload)


class Context:
  def __init__(self, milliseconds_left: int):
    self.milliseconds_left = milliseconds_left

  def get_remaining_time_in_millis(self):
    return self.milliseconds_left


class Client:
  def __init__(self):
    self.invokes = []

  def invoke(self, FunctionName: str, InvocationType: str, Payload: Dict[str, Any]):
    self.invokes.append({
      "name": FunctionName,
      "type": InvocationType,
      "payload": Payload
    })

    return {
      "ResponseMetadata": {
        "HTTPStatusCode": 202
      }
    }

def create_event_from_payload(database: Database, payload: Dict[str, Any], params: Dict[str, Any]):
  def load():
    return params

  base = {
    "test": True,
    "client": Client(),
    "load_func": load,
    "s3": database,
  }

  return {**base, **payload}

def create_event(database: Database, table_name: str, key: str, params: Dict[str, Any], offsets=None):
  return create_event_from_payload(database, create_payload(table_name, key, int(key.split("/")[0]), offsets=offsets), params)


def create_context(params):
  return Context(params["timeout"])
