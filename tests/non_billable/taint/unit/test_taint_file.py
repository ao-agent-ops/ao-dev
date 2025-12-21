# TODO: Revisit Taint files.

# """Unit tests for TaintFile class.

# NOTE: TaintFile functionality is not currently supported in the unified TaintWrapper.
# These tests are commented out until TaintFile is reimplemented.
# """

# import pytest
# import os
# import tempfile
# from ....utils import cleanup_taint_db


# class TestTaintFile:
#     """Test suite for TaintFile class."""

#     def setup_method(self):
#         """Clean up taint database before each test method"""
#         cleanup_taint_db()

#     def test_creation(self):
#         """Test TaintFile creation and initialization."""
#         # Create a temporary file
#         with tempfile.NamedTemporaryFile(mode="w", delete=False) as tmp:
#             tmp_path = tmp.name
#             tmp.write("test content")

#         try:
#             # Test wrapping existing file object
#             with open(tmp_path, "r") as f:
#                 tf = TaintFile(f, mode="r", taint_origin="test_source")
#                 assert tf._mode == "r"
#                 assert tf._taint_origin == ["test_source"]
#                 assert not tf.closed
#                 assert tf.name == tmp_path
#                 assert tf.mode == "r"

#             # Test with no taint origin (should use filename)
#             with open(tmp_path, "r") as f:
#                 tf = TaintFile(f, mode="r")
#                 expected_origin = f"file:{tmp_path}"
#                 assert tf._taint_origin == [expected_origin]

#             # Test with list taint origin
#             with open(tmp_path, "r") as f:
#                 tf = TaintFile(f, mode="r", taint_origin=["source1", "source2"])
#                 assert tf._taint_origin == ["source1", "source2"]

#             # Test invalid taint origin
#             with open(tmp_path, "r") as f:
#                 with pytest.raises(TypeError):
#                     TaintFile(f, taint_origin={})

#         finally:
#             os.unlink(tmp_path)

#     def test_class_method_open(self):
#         """Test TaintFile.open class method."""
#         # Create a temporary file
#         with tempfile.NamedTemporaryFile(mode="w", delete=False) as tmp:
#             tmp_path = tmp.name
#             tmp.write("test content\nline 2\n")

#         try:
#             # Test opening with default taint
#             tf = TaintFile.open(tmp_path, "r")
#             assert tf._taint_origin == [f"file:{tmp_path}"]
#             assert tf.mode == "r"
#             content = tf.read()
#             assert isinstance(content, TaintStr)
#             assert get_taint_origins(content) == [f"file:{tmp_path}"]
#             tf.close()

#             # Test opening with custom taint
#             tf = TaintFile.open(tmp_path, "r", taint_origin="custom_source")
#             assert tf._taint_origin == ["custom_source"]
#             content = tf.read()
#             assert get_taint_origins(content) == ["custom_source"]
#             tf.close()

#         finally:
#             os.unlink(tmp_path)

#     def test_convenience_function(self):
#         """Test open_with_taint convenience function."""
#         with tempfile.NamedTemporaryFile(mode="w", delete=False) as tmp:
#             tmp_path = tmp.name
#             tmp.write("convenience test")

#         try:
#             tf = open_with_taint(tmp_path, "r", taint_origin="convenience")
#             assert isinstance(tf, TaintFile)
#             assert tf._taint_origin == ["convenience"]
#             content = tf.read()
#             assert isinstance(content, TaintStr)
#             assert get_taint_origins(content) == ["convenience"]
#             tf.close()

#         finally:
#             os.unlink(tmp_path)

#     def test_read_operations(self):
#         """Test read(), readline(), readlines() methods."""
#         test_content = "Line 1: Hello\nLine 2: World\nLine 3: Test\n"

#         with tempfile.NamedTemporaryFile(mode="w", delete=False) as tmp:
#             tmp_path = tmp.name
#             tmp.write(test_content)

#         try:
#             # Test read()
#             with open_with_taint(tmp_path, "r", taint_origin="read_test") as tf:
#                 content = tf.read()
#                 assert isinstance(content, TaintStr)
#                 assert str(content) == test_content
#                 assert get_taint_origins(content) == ["read_test"]

#             # Test read() with size limit
#             with open_with_taint(tmp_path, "r", taint_origin="read_limit") as tf:
#                 partial = tf.read(10)
#                 assert isinstance(partial, TaintStr)
#                 assert str(partial) == "Line 1: He"
#                 assert get_taint_origins(partial) == ["read_limit"]

#             # Test readline()
#             with open_with_taint(tmp_path, "r", taint_origin="readline_test") as tf:
#                 line1 = tf.readline()
#                 assert isinstance(line1, TaintStr)
#                 assert str(line1) == "Line 1: Hello\n"
#                 assert get_taint_origins(line1) == ["readline_test"]

#                 line2 = tf.readline()
#                 assert str(line2) == "Line 2: World\n"
#                 assert get_taint_origins(line2) == ["readline_test"]

#             # Test readlines()
#             with open_with_taint(tmp_path, "r", taint_origin="readlines_test") as tf:
#                 lines = tf.readlines()
#                 assert len(lines) == 3
#                 assert all(isinstance(line, TaintStr) for line in lines)
#                 assert str(lines[0]) == "Line 1: Hello\n"
#                 assert str(lines[1]) == "Line 2: World\n"
#                 assert str(lines[2]) == "Line 3: Test\n"
#                 assert all(get_taint_origins(line) == ["readlines_test"] for line in lines)

#         finally:
#             os.unlink(tmp_path)

#     def test_write_operations(self):
#         """Test write() and writelines() methods."""
#         with tempfile.NamedTemporaryFile(mode="w", delete=False) as tmp:
#             tmp_path = tmp.name

#         try:
#             # Test write() with tainted data
#             tainted_data = TaintStr("Tainted content\n", taint_origin="input_source")
#             normal_data = "Normal content\n"

#             with open_with_taint(tmp_path, "w", taint_origin="file_source") as tf:
#                 bytes_written1 = tf.write(tainted_data)
#                 bytes_written2 = tf.write(normal_data)
#                 assert bytes_written1 == len("Tainted content\n")
#                 assert bytes_written2 == len("Normal content\n")

#             # Verify content was written correctly
#             with open(tmp_path, "r") as f:
#                 content = f.read()
#                 assert content == "Tainted content\nNormal content\n"

#             # Test writelines()
#             lines = [
#                 TaintStr("Line 1: tainted\n", taint_origin="line1"),
#                 "Line 2: normal\n",
#                 TaintStr("Line 3: also tainted\n", taint_origin="line3"),
#             ]

#             with open_with_taint(tmp_path, "w", taint_origin="write_file") as tf:
#                 tf.writelines(lines)

#             # Verify content
#             with open(tmp_path, "r") as f:
#                 content = f.read()
#                 expected = "Line 1: tainted\nLine 2: normal\nLine 3: also tainted\n"
#                 assert content == expected

#         finally:
#             os.unlink(tmp_path)

#     def test_iteration(self):
#         """Test file iteration (__iter__ and __next__)."""
#         test_content = "Line 1\nLine 2\nLine 3\n"

#         with tempfile.NamedTemporaryFile(mode="w", delete=False) as tmp:
#             tmp_path = tmp.name
#             tmp.write(test_content)

#         try:
#             with open_with_taint(tmp_path, "r", taint_origin="iter_test") as tf:
#                 lines = []
#                 for line in tf:
#                     lines.append(line)

#                 assert len(lines) == 3
#                 assert all(isinstance(line, TaintStr) for line in lines)
#                 assert str(lines[0]) == "Line 1\n"
#                 assert str(lines[1]) == "Line 2\n"
#                 assert str(lines[2]) == "Line 3\n"
#                 assert all(get_taint_origins(line) == ["iter_test"] for line in lines)

#         finally:
#             os.unlink(tmp_path)

#     def test_context_manager(self):
#         """Test context manager support (__enter__ and __exit__)."""
#         with tempfile.NamedTemporaryFile(mode="w", delete=False) as tmp:
#             tmp_path = tmp.name
#             tmp.write("context test")

#         try:
#             # Test context manager
#             with open_with_taint(tmp_path, "r", taint_origin="context_test") as tf:
#                 assert not tf.closed
#                 content = tf.read()
#                 assert isinstance(content, TaintStr)
#                 assert get_taint_origins(content) == ["context_test"]

#             # File should be closed after context exit
#             assert tf.closed

#         finally:
#             os.unlink(tmp_path)

#     def test_file_positioning(self):
#         """Test seek(), tell() methods."""
#         test_content = "0123456789abcdef"

#         with tempfile.NamedTemporaryFile(mode="w+", delete=False) as tmp:
#             tmp_path = tmp.name
#             tmp.write(test_content)

#         try:
#             with open_with_taint(tmp_path, "r+", taint_origin="position_test") as tf:
#                 # Test tell()
#                 assert tf.tell() == 0

#                 # Test seek()
#                 tf.seek(5)
#                 assert tf.tell() == 5

#                 # Read from position
#                 data = tf.read(3)
#                 assert isinstance(data, TaintStr)
#                 assert str(data) == "567"
#                 assert get_taint_origins(data) == ["position_test"]
#                 assert tf.tell() == 8

#                 # Seek to end
#                 tf.seek(0, 2)  # SEEK_END
#                 end_pos = tf.tell()
#                 assert end_pos == len(test_content)

#         finally:
#             os.unlink(tmp_path)

#     def test_file_properties(self):
#         """Test file properties and methods."""
#         with tempfile.NamedTemporaryFile(mode="w+", delete=False, encoding="utf-8") as tmp:
#             tmp_path = tmp.name
#             tmp.write("property test")

#         try:
#             with open_with_taint(tmp_path, "r+", encoding="utf-8", taint_origin="prop_test") as tf:
#                 # Test properties
#                 assert tf.name == tmp_path
#                 assert tf.mode == "r+"
#                 assert tf.encoding == "utf-8"
#                 assert not tf.closed

#                 # Test capability methods
#                 assert tf.readable() is True
#                 assert tf.writable() is True
#                 assert tf.seekable() is True

#                 # Test fileno() (should return an integer)
#                 fd = tf.fileno()
#                 assert isinstance(fd, int)

#                 # Test isatty() (should return False for regular files)
#                 assert tf.isatty() is False

#         finally:
#             os.unlink(tmp_path)

#     def test_flush_and_truncate(self):
#         """Test flush() and truncate() methods."""
#         with tempfile.NamedTemporaryFile(mode="w+", delete=False) as tmp:
#             tmp_path = tmp.name
#             tmp.write("initial content")

#         try:
#             with open_with_taint(tmp_path, "r+", taint_origin="flush_test") as tf:
#                 # Write some data
#                 tf.write("new data")

#                 # Test flush() (should not raise an error)
#                 tf.flush()

#                 # Test truncate()
#                 tf.seek(0)
#                 tf.truncate(5)
#                 tf.seek(0)

#                 content = tf.read()
#                 assert len(str(content)) == 5
#                 assert isinstance(content, TaintStr)

#         finally:
#             os.unlink(tmp_path)

#     def test_binary_mode(self):
#         """Test binary file operations."""
#         test_data = b"binary test data\x00\x01\x02"

#         with tempfile.NamedTemporaryFile(mode="wb", delete=False) as tmp:
#             tmp_path = tmp.name
#             tmp.write(test_data)

#         try:
#             # Test binary read
#             with open_with_taint(tmp_path, "rb", taint_origin="binary_test") as tf:
#                 data = tf.read()
#                 # Binary data should be returned as bytes (not tainted)
#                 assert isinstance(data, bytes)
#                 assert data == test_data

#             # Test binary write
#             new_data = b"new binary data"
#             with open_with_taint(tmp_path, "wb", taint_origin="binary_write") as tf:
#                 bytes_written = tf.write(new_data)
#                 assert bytes_written == len(new_data)

#             # Verify
#             with open(tmp_path, "rb") as f:
#                 content = f.read()
#                 assert content == new_data

#         finally:
#             os.unlink(tmp_path)

#     def test_repr_str(self):
#         """Test __repr__ method."""
#         with tempfile.NamedTemporaryFile(mode="w", delete=False) as tmp:
#             tmp_path = tmp.name
#             tmp.write("repr test")

#         try:
#             with open(tmp_path, "r") as f:
#                 tf = TaintFile(f, mode="r", taint_origin="repr_test")
#                 repr_str = repr(tf)
#                 assert "TaintFile" in repr_str
#                 assert "repr_test" in repr_str
#                 tf.close()

#         finally:
#             os.unlink(tmp_path)

#     def test_error_handling(self):
#         """Test error handling for invalid operations."""
#         with tempfile.NamedTemporaryFile(mode="w", delete=False) as tmp:
#             tmp_path = tmp.name
#             tmp.write("error test")

#         try:
#             # Test reading from write-only file
#             with open_with_taint(tmp_path, "w", taint_origin="write_only") as tf:
#                 with pytest.raises(Exception):  # Should raise UnsupportedOperation or similar
#                     tf.read()

#             # Test operations on closed file
#             tf = open_with_taint(tmp_path, "r", taint_origin="closed_test")
#             tf.close()

#             with pytest.raises(ValueError):  # Should raise ValueError for operations on closed file
#                 tf.read()

#         finally:
#             os.unlink(tmp_path)

#     def test_taint_preservation_complex(self):
#         """Test complex taint preservation scenarios."""
#         # Clean up any existing taint data before the test
#         cleanup_taint_db()
#         with tempfile.NamedTemporaryFile(mode="w+", delete=False) as tmp:
#             tmp_path = tmp.name
#             tmp.write("initial content\n")

#         try:
#             # Write tainted data, then read it back
#             tainted_input = TaintStr("User input data\n", taint_origin="user_input")

#             with open_with_taint(tmp_path, "w", taint_origin="write_session") as tf:
#                 tf.write(tainted_input)

#             # Read it back with different taint origin
#             with open_with_taint(tmp_path, "r", taint_origin="read_session") as tf:
#                 content = tf.read()
#                 # Should have taint from read session (file-level taint)
#                 assert get_taint_origins(content) == ["read_session"]

#                 # The original user_input taint is not preserved in the file
#                 # (that would require a separate metadata system)
#                 assert str(content) == "User input data\n"

#         finally:
#             os.unlink(tmp_path)
