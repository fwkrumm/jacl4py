"""Verify preserved custom levels, handler settings, and logging side effects."""

import io
import logging
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from jacl4py.logger import (
    INTERNAL_DEBUG, INTERNAL_INFO, JacLogger, LogDir, delete_logger, get_logger,
)


class TestLoggerBehavior(unittest.TestCase):
    """Cover the original logger's public behavior without changing its code."""

    def setUp(self):
        self.name = f"behavior_{uuid.uuid4().hex}"

    def tearDown(self):
        delete_logger(self.name)

    def test_import_keeps_standard_class_and_registers_level_names(self):
        """Importing keeps the standard logger class and registers level names."""
        self.assertIs(logging.getLoggerClass(), logging.Logger)
        self.assertEqual(INTERNAL_DEBUG, 5)
        self.assertEqual(INTERNAL_INFO, 7)
        self.assertEqual(logging.getLevelName(5), "INTERNAL_DEBUG")
        self.assertEqual(logging.getLevelName(7), "INTERNAL_INFO")

    def test_custom_levels_emit_and_respect_threshold(self):
        """Internal messages honor the configured logger and handler thresholds."""
        logger = get_logger(self.name, console_log_level=None, file_log_level=None)
        output = io.StringIO()
        handler = logging.StreamHandler(output)
        logger.addHandler(handler)
        logger.idebug("debug %s", "message")
        logger.iinfo("info %s", "message")
        self.assertEqual(output.getvalue(), "debug message\ninfo message\n")
        logger.setLevel(logging.WARNING)
        logger.idebug("hidden debug")
        logger.iinfo("hidden info")
        self.assertEqual(output.getvalue(), "debug message\ninfo message\n")
        self.assertEqual(handler.level, logging.NOTSET)

    def test_disabled_handlers_leave_logger_unconfigured(self):
        """Disabling both outputs leaves no handlers and prevents propagation."""
        logger = get_logger(self.name, console_log_level=None, file_log_level=None)
        self.assertEqual(logger.handlers, [])
        self.assertEqual(logger.level, INTERNAL_DEBUG)
        self.assertFalse(logger.propagate)

    def test_default_file_path_rotation_and_content(self):
        """Default files use the logger name and retain internal messages."""
        with tempfile.TemporaryDirectory() as directory:
            with patch("jacl4py.logger.tempfile.gettempdir", return_value=directory), \
                    patch("jacl4py.logger.uuid4", return_value=uuid.UUID("12345678" + "0" * 24)):
                logger = get_logger(self.name, console_log_level=None)
            handler = logger.handlers[0]
            expected = Path(directory) / (self.name + "12345678") / f"{self.name}.log"
            self.assertEqual(Path(handler.baseFilename), expected)
            self.assertEqual(handler.when, "MIDNIGHT")
            self.assertEqual(handler.backupCount, 30)
            self.assertEqual(handler.encoding, "utf-8")
            self.assertEqual(handler.level, INTERNAL_DEBUG)
            logger.idebug("retained debug")
            logger.iinfo("retained info")
            handler.flush()
            content = expected.read_text(encoding="utf-8")
            self.assertIn("INTERNAL_DEBUG - retained debug", content)
            self.assertIn("INTERNAL_INFO - retained info", content)
            handler.close()
            logger.removeHandler(handler)

    def test_explicit_default_directory_uses_logger_name(self):
        """The explicit default directory matches the implicit default."""
        with tempfile.TemporaryDirectory() as directory:
            with patch("jacl4py.logger.tempfile.gettempdir", return_value=directory), \
                    patch("jacl4py.logger.uuid4", return_value=uuid.UUID("12345678" + "0" * 24)):
                logger = get_logger(self.name, console_log_level=None, log_dir=LogDir.DEFAULT)
            try:
                self.assertEqual(
                    Path(logger.handlers[0].baseFilename).parent,
                    Path(directory) / (self.name + "12345678"),
                )
            finally:
                for handler in list(logger.handlers):
                    handler.close()
                    logger.removeHandler(handler)

    def test_none_directory_disables_files_but_keeps_console(self):
        """A None directory skips filesystem setup without disabling the console."""
        with patch("jacl4py.logger.tempfile.gettempdir") as gettempdir:
            with patch.object(Path, "mkdir") as mkdir:
                logger = get_logger(self.name, log_dir=None, use_colored_output=False)
        gettempdir.assert_not_called()
        mkdir.assert_not_called()
        self.assertEqual(len(logger.handlers), 1)
        self.assertIs(type(logger.handlers[0]), logging.StreamHandler)

    def test_none_directory_and_console_level_disable_all_handlers(self):
        """A None directory and console level disable both outputs."""
        logger = get_logger(self.name, log_dir=None, console_log_level=None)
        self.assertEqual(logger.handlers, [])

    def test_colored_console_receives_original_configuration(self):
        """Colored output receives the expected level styles and format."""
        with patch("jacl4py.logger.coloredlogs.install") as install:
            logger = get_logger(self.name, file_log_level=None)
        configuration = install.call_args.kwargs
        self.assertEqual(configuration["level"], logging.INFO)
        self.assertIs(configuration["logger"], logger)
        self.assertIn("internal_debug", configuration["level_styles"])
        self.assertIn("internal_info", configuration["level_styles"])
        self.assertIn("%(name)s", configuration["fmt"])

    def test_existing_standard_logger_is_untouched(self):
        """An existing standard logger does not conflict with the package logger."""
        standard = logging.getLogger(self.name)
        logger = get_logger(self.name, log_dir=None, console_log_level=None)
        self.assertIsInstance(logger, JacLogger)
        self.assertIsNot(logger, standard)
        self.assertIs(logging.getLogger(self.name), standard)
        self.assertEqual(standard.handlers, [])
