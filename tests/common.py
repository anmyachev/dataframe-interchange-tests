from typing import Any, Callable, Dict, NamedTuple

import pytest
from hypothesis import assume
from hypothesis import strategies as st

from .api import DataFrame

__all__ = ["lib_params", "lib_to_linfo"]

TopLevelDataFrame = Any


class LibraryInfo(NamedTuple):
    strategy: st.SearchStrategy[TopLevelDataFrame]
    from_dataframe: Callable[[TopLevelDataFrame], DataFrame]
    frame_equal: Callable[[TopLevelDataFrame, DataFrame], bool]
    get_compliant_dataframe: Callable[[TopLevelDataFrame], DataFrame] = lambda df: (
        df.__dataframe__()["dataframe"]
    )


lib_params: list = []
lib_to_linfo: Dict[str, LibraryInfo] = {}

try:
    import numpy as np
    import pandas as pd
    from hypothesis.extra import pandas as pds
    from pandas.api.exchange import from_dataframe as pandas_from_dataframe
except ImportError as e:
    lib_params.append(pytest.param("pandas", marks=pytest.mark.skip(reason=e.msg)))
else:
    valid_dtypes = [np.bool_]  # TODO: str, datetimes, categories
    for kind in ["int", "uint"]:
        for bitwidth in [8, 16, 32, 64]:
            valid_dtypes.append(np.dtype(f"{kind}{bitwidth}"))
    for bitwidth in [32, 64]:
        valid_dtypes.append(np.dtype(f"float{bitwidth}"))

    @st.composite
    def dataframes(draw) -> st.SearchStrategy[pd.DataFrame]:
        colnames_strat = st.from_regex("[a-z]+", fullmatch=True)
        colnames = draw(st.lists(colnames_strat, min_size=1, unique=True))
        columns = []
        for colname in colnames:
            dtype = draw(st.sampled_from(valid_dtypes))
            column = pds.column(colname, dtype=dtype)
            columns.append(column)
        df = draw(pds.data_frames(columns))
        assume(df.shape[0] != 0)  # TODO: generate empty dataframes
        return df

    linfo = LibraryInfo(
        strategy=dataframes(),
        from_dataframe=pandas_from_dataframe,
        frame_equal=lambda df1, df2: df1.equals(df2),
        get_compliant_dataframe=lambda df: df.__dataframe__(),
    )
    lib_to_linfo["pandas"] = linfo
    lib_params.append("pandas")

try:
    import numpy as np
    import vaex
    from vaex.dataframe_protocol import from_dataframe_to_vaex as vaex_from_dataframe
except ImportError as e:
    lib_params.append(pytest.param("vaex", marks=pytest.mark.skip(reason=e.msg)))
else:

    def vaex_frame_equal(df1: DataFrame, df2: DataFrame) -> bool:
        same_shape = df1.shape == df2.shape
        if not same_shape:
            return False
        columns = df1.get_column_names()
        same_cols = columns == df2.get_column_names()
        if not same_cols:
            return False
        for col in columns:
            if not np.array_equal(df1[col].values, df2[col].values, equal_nan=True):
                return False
        return True

    linfo = LibraryInfo(
        strategy=st.just(vaex.from_dict({"n": [42]})),
        from_dataframe=vaex_from_dataframe,
        frame_equal=vaex_frame_equal,
        get_compliant_dataframe=lambda df: df.__dataframe__(),
    )
    lib_to_linfo["vaex"] = linfo
    lib_params.append("vaex")

try:
    import modin
    import ray  # noqa: F401
    from modin.config import Engine
    from modin.pandas.utils import from_dataframe as modin_from_dataframe
except ImportError as e:
    lib_params.append(pytest.param("modin", marks=pytest.mark.skip(reason=e.msg)))
else:
    Engine.put("ray")
    linfo = LibraryInfo(
        strategy=st.just(modin.pandas.DataFrame({"n": [42]})),
        from_dataframe=modin_from_dataframe,
        frame_equal=lambda df1, df2: df1.equals(df2),
    )
    lib_to_linfo["modin"] = linfo
    lib_params.append("modin")


if __name__ == "__main__":
    print(f"loaded libraries: {', '.join(lib_to_linfo.keys())}")
