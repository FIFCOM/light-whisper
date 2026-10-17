"""Collect ONNX provider plugins without the standalone C API library."""

from pathlib import PureWindowsPath

from PyInstaller.utils.hooks import collect_dynamic_libs


# Normal dependency analysis can still collect the core if a PE file imports it.
binaries = [
    (source, destination)
    for source, destination in collect_dynamic_libs("onnxruntime")
    if not (
        PureWindowsPath(source).name.casefold() == "onnxruntime.dll"
        and PureWindowsPath(destination).as_posix().casefold() == "onnxruntime/capi"
    )
]
