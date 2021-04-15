import itertools
import os
from typing import (
    Optional,
)

from kb_notes.application import Application
from kb_notes.helpers import (
    buffer_is_empty,
    disable_deoplete,
    char_under_cursor,
    char_after_cursor,
    current_note_name,
)
from kb_notes.highlight import Highlight
from kb_notes.note import Note
from kb_notes.config import (
    LINK_SUGGESTION_SINK_FIND_AND_REPLACE_NOTE,
    LINK_SUGGESTION_SINK_INSERT_NOTE,
    OPEN_NOTE_SINK,
)
from kb_notes.preview import Preview


class Link:
    def __init__(
        self,
        app: Application,
        highlight: Highlight,
        note: Note,
        preview: Preview,
    ):
        self.app = app
        self.highlight = highlight
        self.note = note
        self.preview = preview

    def get_note_name_under_cursor(self) -> Optional[str]:
        cursor_position = self.app.nvim.current.window.cursor
        line_position = cursor_position[0] - 1
        row_position = cursor_position[1]

        for _, line, start, end in self.highlight.current_buffer_wiki_links:
            if line == line_position and start <= row_position <= end:
                return self.app.nvim.current.line.encode()[start + 2 : end - 2].decode()

        return None

    def command_open_note_sink(self, args):
        note_name = "".join(args)

        self.app.nvim.command(
            f"e {self.app.note_finder.get_full_path_for_note(note_name)}"
        )

    def command_get_links(self):
        source = {
            *self.app.note_finder.find_backlinks(current_note_name(self.app.nvim)),
            *self.app.note_finder.find_children(current_note_name(self.app.nvim)),
            *self.app.note_finder.find_links_in_lines(self.app.nvim.current.buffer),
        }

        if parent := self.app.note_finder.find_parent(current_note_name(self.app.nvim)):
            if os.path.isfile(self.app.note_finder.get_full_path_for_note(parent)):
                source.add(parent)

        self.preview.fzf_with_preview(
            source=sorted(source),
            sink=OPEN_NOTE_SINK,
            location=self.app.config.note_folder,
        )

    def open_note(self, note_name: str):
        self.app.nvim.command(
            f"e {self.app.note_finder.get_full_path_for_note(note_name)}"
        )

        if buffer_is_empty(self.app.nvim.current.buffer):
            self.note.insert_template(note_name)
            self.app.nvim.command("w")

            # New file is created, link in previous buffer should be marked as existing
            self.highlight.get_highlights.cache_clear()

    def command_open_link(self):
        if self.highlight.is_wikilink_under_cursor:
            note_name = self.get_note_name_under_cursor()
            self.open_note(note_name)
        else:
            if char_under_cursor(self.app.nvim) == "[" and char_after_cursor(
                self.app.nvim
            ):
                # possible it's begging of url
                # for some reason [ in the begging of url is treated as mkdDelimiter (plasticboy/vim-markdown)
                self.app.nvim.feedkeys("l")

            if self.highlight.is_url_under_cursor:
                self.app.nvim.feedkeys("gx")
            else:
                self.app.nvim.out_write("No link under cursor\n")

    def command_link_suggestion_sink_insert_note(self, args):
        note_name = "".join(args)

        with disable_deoplete(self.app.nvim):
            self.app.nvim.feedkeys(f"a[[{note_name}]]")
            self.app.nvim.command("stopinsert")

    def command_link_suggestion_sink_find_note_and_replace(self, args):
        note_name = "".join(args)

        if char_under_cursor(self.app.nvim) == "[" and char_after_cursor(self.app.nvim):
            # if fist bracket
            self.app.nvim.feedkeys("f[")

        with disable_deoplete(self.app.nvim):
            self.app.nvim.feedkeys(f'"_ci[{note_name}')
            self.app.nvim.command("stopinsert")

    def command_link_suggestion(self):
        if self.highlight.is_wikilink_under_cursor:
            note_name = self.get_note_name_under_cursor()

            sink = LINK_SUGGESTION_SINK_FIND_AND_REPLACE_NOTE
        else:
            note_name = None
            sink = LINK_SUGGESTION_SINK_INSERT_NOTE

        self.preview.fzf_with_preview(
            source=self.app.note_finder.find_notes(),
            sink=sink,
            location=self.app.config.note_folder,
            search_term=note_name,
        )

    def command_go_to_parent_note(self):
        parent_note = self.app.note_finder.find_parent(current_note_name(self.app.nvim))

        if not parent_note:
            self.app.nvim.out_write("Current note is the root\n")
            return

        self.open_note(parent_note)

    def command_show_connected_notes_for_link(self):
        note = self.get_note_name_under_cursor()
        if not note:
            self.app.nvim.out_write("No link under cursor\n")
            return

        if os.path.isfile(self.app.note_finder.get_full_path_for_note(note)):
            with open(self.app.note_finder.get_full_path_for_note(note)) as f:
                note_content = f.readlines()
        else:
            note_content = []

        self.preview.fzf_with_preview(
            source=[
                *([note] if note_content else []),
                *self.app.note_finder.find_backlinks(note),
                *self.app.note_finder.find_children(note),
                *self.app.note_finder.find_links_in_lines(note_content),
            ],
            sink=OPEN_NOTE_SINK,
            location=self.app.config.note_folder,
        )
