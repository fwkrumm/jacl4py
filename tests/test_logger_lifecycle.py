"""Cover explicit logger replacement and deletion."""

import logging
import tempfile
import unittest
import uuid
import warnings
from pathlib import Path
from unittest.mock import patch

from jacl4py.logger import JacLogger, ResourceNotInitializedError, delete_logger, get_logger


class TestLoggerLifecycle(unittest.TestCase):
    """Verify replacement, deletion, and stale-reference handling."""

    def setUp(self):
        self.name = f"lifecycle_{uuid.uuid4().hex}"

    def tearDown(self):
        delete_logger(self.name + ".child")
        delete_logger(self.name)

    def test_reinit_replaces_logger_and_applies_settings_without_warning(self):
        """Reinitialization replaces the instance and applies settings silently."""
        original = get_logger(self.name, log_dir=None, use_colored_output=False)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            replacement = get_logger(
                self.name,
                reinit_if_exists=True,
                log_dir=None,
                use_colored_output=False,
                console_log_level=logging.ERROR,
            )
        self.assertEqual(caught, [])
        self.assertIsNot(original, replacement)
        self.assertIsInstance(replacement, JacLogger)
        self.assertTrue(original.disabled)
        self.assertEqual(original.handlers, [])
        self.assertEqual(len(replacement.handlers), 1)
        self.assertEqual(replacement.handlers[0].level, logging.ERROR)

    def test_delete_closes_file_handler_and_preserves_file(self):
        """Deleting releases file handles without removing existing log files."""
        with tempfile.TemporaryDirectory() as directory:
            logger = get_logger(self.name, console_log_level=None, log_dir=directory)
            self.addCleanup(delete_logger, self.name)
            handler = logger.handlers[0]
            filename = Path(handler.baseFilename)
            self.assertTrue(delete_logger(self.name))
            self.assertIsNone(handler.stream)
            self.assertTrue(filename.exists())
            self.assertNotIn(self.name, logging.Logger.manager.loggerDict)
            self.assertTrue(logger.disabled)
            self.assertEqual(logger.handlers, [])

    def test_delete_missing_logger_does_not_create_it(self):
        """Deleting an unknown name leaves the registry unchanged."""
        self.assertFalse(delete_logger(self.name))
        self.assertNotIn(self.name, logging.Logger.manager.loggerDict)

    def test_delete_leaves_standard_logger_untouched(self):
        """Package deletion does not change standard loggers or their handlers."""
        logger = logging.getLogger(self.name)
        self.assertIs(type(logger), logging.Logger)
        handler = logging.NullHandler()
        logger.addHandler(handler)
        self.addCleanup(logger.removeHandler, handler)
        self.addCleanup(handler.close)
        with patch.object(handler, "close", wraps=handler.close) as close:
            self.assertFalse(delete_logger(self.name))
        close.assert_not_called()
        self.assertFalse(logger.disabled)
        self.assertEqual(logger.handlers, [handler])
        self.assertIs(logging.getLogger(self.name), logger)

    def test_deleted_logger_raises_for_standard_and_custom_log_methods(self):
        """Deleted references raise before filtering any message by level."""
        logger = get_logger(self.name, console_log_level=None, log_dir=None)
        logger.setLevel(logging.CRITICAL)
        delete_logger(self.name)
        for method in (
            "debug", "info", "warning", "error", "exception", "critical",
            "fatal", "iinfo", "idebug",
        ):
            with self.subTest(method=method):
                with self.assertRaisesRegex(ResourceNotInitializedError, self.name):
                    getattr(logger, method)("deleted logger")
        with self.assertRaises(ResourceNotInitializedError):
            logger.log(logging.INFO, "deleted logger")

    def test_reinit_invalidates_old_reference_but_new_logger_remains_usable(self):
        """Reinitialization invalidates only the old logger reference."""
        original = get_logger(self.name, console_log_level=None, log_dir=None)
        replacement = get_logger(
            self.name, console_log_level=None, log_dir=None, reinit_if_exists=True
        )
        with self.assertRaises(ResourceNotInitializedError):
            original.info("old reference")
        replacement.info("new reference")

    def test_disabled_logger_without_deletion_does_not_raise(self):
        """Ordinary disabled loggers still ignore messages without raising."""
        logger = get_logger(self.name, console_log_level=None, log_dir=None)
        logger.disabled = True
        logger.info("disabled logger")

    def test_reinit_replaces_logger_without_handlers(self):
        """Reinitialization replaces an instance even when it has no handlers."""
        original = get_logger(self.name, console_log_level=None, log_dir=None)
        replacement = get_logger(
            self.name, console_log_level=None, log_dir=None, reinit_if_exists=True
        )
        self.assertIsNot(original, replacement)

    def test_children_reconnect_after_deletion_and_recreation(self):
        """Child loggers reconnect when their deleted parent is recreated."""
        original = get_logger(self.name, console_log_level=None, log_dir=None)
        child = get_logger(self.name + ".child", console_log_level=None, log_dir=None)
        self.assertIs(child.parent, original)
        self.assertTrue(delete_logger(self.name))
        self.assertIsNot(child.parent, original)
        self.assertFalse(delete_logger(self.name))
        replacement = get_logger(self.name, console_log_level=None, log_dir=None)
        self.assertIs(child.parent, replacement)
