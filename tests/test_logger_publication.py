"""Regression coverage for publication readiness and isolated file writers."""

import multiprocessing
import tempfile
import time
import unittest
import uuid
import warnings
from concurrent.futures import ThreadPoolExecutor
from importlib.metadata import version
from pathlib import Path
from unittest.mock import patch

from jacl4py import __version__
from jacl4py import logger as logger_module
from jacl4py.logger import delete_logger, get_logger


def _child_file(name, directory, connection):
    try:
        logger = get_logger(name, log_dir=directory, console_log_level=None)
        logger.info("child message")
        connection.send(logger.handlers[0].baseFilename)
    finally:
        delete_logger(name)
        connection.close()


class TestPublicationReadiness(unittest.TestCase):
    """Verify versions, safe paths, lifecycle locking, and writer isolation."""

    def setUp(self):
        self.name = "publication_" + uuid.uuid4().hex
        self.addCleanup(delete_logger, self.name)

    def test_version_matches_metadata_and_logger_module(self):
        """Built metadata and both import locations share one version."""
        self.assertEqual(__version__, version("jacl4py"))
        self.assertEqual(__version__, logger_module.__version__)

    def test_path_names_cannot_escape_directory(self):
        """Unsafe names stay inside both default and explicit directories."""
        with tempfile.TemporaryDirectory() as directory:
            for name in ("../../outside", "/absolute", "C:\\outside", "..", "bad\x00name"):
                for default in (True, False):
                    with self.subTest(name=name, default=default):
                        with patch("jacl4py.logger.tempfile.gettempdir", return_value=directory):
                            options = {} if default else {"log_dir": directory}
                            logger = get_logger(name, console_log_level=None, **options)
                        try:
                            filename = Path(logger.handlers[0].baseFilename)
                            self.assertTrue(filename.resolve().is_relative_to(Path(directory)))
                            self.assertEqual(filename.parent.parent if default else filename.parent,
                                             Path(directory))
                        finally:
                            delete_logger(name)

    def test_default_path_retries_uuid_collision(self):
        """An occupied UUID directory is never reused."""
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / (self.name + "12345678")).mkdir()
            identifiers = [uuid.UUID(prefix + "0" * 24) for prefix in ("12345678", "87654321")]
            with patch("jacl4py.logger.tempfile.gettempdir", return_value=directory), \
                    patch("jacl4py.logger.uuid4", side_effect=identifiers):
                logger = get_logger(self.name, console_log_level=None)
            try:
                self.assertEqual(Path(logger.handlers[0].baseFilename).parent.name,
                                 self.name + "87654321")
            finally:
                delete_logger(self.name)

    def test_explicit_directory_retries_filename_collision(self):
        """Existing files cannot be opened by a second writer on collision."""
        with tempfile.TemporaryDirectory() as directory:
            existing = Path(directory) / (self.name + "12345678.log")
            existing.write_text("preserved", encoding="utf-8")
            identifiers = [uuid.UUID(prefix + "0" * 24) for prefix in ("12345678", "87654321")]
            with patch("jacl4py.logger.uuid4", side_effect=identifiers):
                logger = get_logger(self.name, log_dir=directory, console_log_level=None)
            try:
                self.assertEqual(Path(logger.handlers[0].baseFilename).name,
                                 self.name + "87654321.log")
                self.assertEqual(existing.read_text(encoding="utf-8"), "preserved")
            finally:
                delete_logger(self.name)

    def test_concurrent_initialization_and_deletion(self):
        """Concurrent callers share one configured instance and delete it once."""
        def create_logger(_index):
            return get_logger(self.name, log_dir=None, use_colored_output=False)

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with ThreadPoolExecutor(max_workers=8) as executor:
                loggers = list(executor.map(create_logger, range(32)))
                self.assertTrue(all(logger is loggers[0] for logger in loggers))
                self.assertEqual(len(loggers[0].handlers), 1)
                deleted = list(executor.map(lambda _index: delete_logger(self.name), range(32)))
        self.assertEqual(sum(deleted), 1)

    def test_rollover_keeps_stable_filename_and_thirty_backups(self):
        """Actual rollovers prune the current writer's backup family."""
        with tempfile.TemporaryDirectory() as directory:
            logger = get_logger(self.name, log_dir=directory, console_log_level=None)
            try:
                handler = logger.handlers[0]
                filename = Path(handler.baseFilename)
                logger.info("before rollover")
                for index in range(35):
                    handler.rolloverAt = int(time.time()) - (40 - index) * 86400
                    handler.doRollover()
                logger.info("after rollover")
                handler.flush()
                self.assertEqual(Path(handler.baseFilename), filename)
                self.assertEqual(len(list(filename.parent.glob(filename.name + ".*"))), 30)
                self.assertIn("after rollover", filename.read_text(encoding="utf-8"))
            finally:
                delete_logger(self.name)

    def test_child_process_gets_separate_file(self):
        """Spawned and forked children never reuse the parent's file writer."""
        with tempfile.TemporaryDirectory() as directory:
            logger = get_logger(self.name, log_dir=directory, console_log_level=None)
            try:
                parent_file = Path(logger.handlers[0].baseFilename)
                for method in multiprocessing.get_all_start_methods():
                    with self.subTest(method=method):
                        context = multiprocessing.get_context(method)
                        receiver, sender = context.Pipe(duplex=False)
                        process = context.Process(target=_child_file,
                                                  args=(self.name, directory, sender))
                        process.start()
                        sender.close()
                        try:
                            self.assertTrue(receiver.poll(20), "Child did not return a file path")
                            child_file = Path(receiver.recv())
                            process.join(20)
                            self.assertEqual(process.exitcode, 0)
                            self.assertNotEqual(parent_file, child_file)
                            self.assertIn("child message", child_file.read_text(encoding="utf-8"))
                        finally:
                            if process.is_alive():
                                process.terminate()
                                process.join()
                            receiver.close()
                            process.close()
                logger.info("parent remains usable")
            finally:
                delete_logger(self.name)