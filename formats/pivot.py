import boto3
import iterator
import util
from iterator import Delimiter, DelimiterPosition, OffsetBounds, Options
from typing import Any, BinaryIO, ClassVar, Dict, List, Optional


class Iterator(iterator.Iterator[None]):
  delimiter: Delimiter = Delimiter(item_token="\n\n", offset_token="\n\n", position=DelimiterPosition.inbetween)
  identifiers: None
  increment: ClassVar[int] = 100  # TODO: Unhardcode

  def __init__(self, obj: Any, offset_bounds: Optional[OffsetBounds] = None):
    iterator.Iterator.__init__(self, Iterator, obj, offset_bounds)

  def combine(cls: Any, objs: List[Any], f: BinaryIO) -> Dict[str, str]:
    pivots: List[int] = []
    file_key: Optional[str] = None
    for obj in objs:
      content: str = util.read(obj, 0, obj.content_length)
      [file_bucket, file_key, pivot_content] = content.split("\n")
      pivot_content: str = pivot_content.strip()
      if len(pivot_content) > 0:
        new_pivots: List[int] = list(map(lambda p: float(p), pivot_content.split("\t")))
        pivots += new_pivots
    assert(file_key is not None)

    pivots.sort()
    super_pivots: List[int] = []
    num_bins = int((len(pivots) + cls.increment) / cls.increment)
    increment = float(len(pivots)) / num_bins

    i: int = 0
    while i < len(pivots):
      x: int = min(round(i), len(pivots) - 1)
      super_pivots.append(pivots[x])
      i += increment

    if super_pivots[-1] != pivots[-1]:
      super_pivots.append(pivots[-1])
    spivots: List[str] = list(map(lambda p: str(p), super_pivots))
    content: str = "{0:s}\n{1:s}\n{2:s}".format(file_bucket, file_key, "\t".join(spivots))
    f.write(str.encode(content))
    return {}


def get_pivot_ranges(bucket_name, key, params={}):
  if "s3" in params:
    s3 = params["s3"]
  else:
    s3 = boto3.resource("s3")
  ranges = []

  obj = s3.Object(bucket_name, key)
  content = util.read(obj, 0, obj.content_length)
  [file_bucket, file_key, pivot_content] = content.split("\n")
  pivots = list(map(lambda p: float(p), pivot_content.split("\t")))

  for i in range(len(pivots) - 1):
    end_range = int(pivots[i + 1])
    ranges.append({
      "range": [int(pivots[i]), end_range],
      "bin": i + 1,
    })

  return file_bucket, file_key, ranges
