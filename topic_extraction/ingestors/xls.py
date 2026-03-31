import openpyxl
import xlrd

from topic_extraction.ingestors.base import BaseIngestor, Conversation

# Default column names for the ypepth consultation format
YPEPTH_COLUMN_MAP = {
    'article': 'Άρθρο',
    'comment': 'Σχόλιο',
}


class XLSIngestor(BaseIngestor):
    """Ingestor for XLS/XLSX files in the ypepth deliberation format.

    Groups comment rows by article title. The article title serves as both
    the article_id and the article text (since XLS files do not contain
    the full article body — only the section heading).

    Args:
        platform: Pilot site identifier to tag on each Conversation.
        column_map: Override default column name mappings.
    """

    def __init__(self, platform: str, column_map: dict | None = None):
        self.platform = platform
        self.column_map = column_map or YPEPTH_COLUMN_MAP

    def load(self, source: str) -> list[Conversation]:
        rows, headers = self._read_rows(source)
        article_col = headers.index(self.column_map['article'])
        comment_col = headers.index(self.column_map['comment'])

        grouped: dict[str, list[str]] = {}
        for row in rows:
            article_title = str(row[article_col]).strip() if row[article_col] else ''
            comment_text = str(row[comment_col]).strip() if row[comment_col] else ''
            if not article_title or not comment_text:
                continue
            if article_title not in grouped:
                grouped[article_title] = []
            grouped[article_title].append(comment_text)

        return [
            Conversation(
                article_id=title,
                platform=self.platform,
                article=title,
                comments=comments,
            )
            for title, comments in grouped.items()
        ]

    def _read_rows(self, source: str):
        """Read all rows from XLS or XLSX file. Returns (data_rows, headers)."""
        if source.lower().endswith('.xlsx'):
            return self._read_xlsx(source)
        return self._read_xls(source)

    def _read_xls(self, source: str):
        wb = xlrd.open_workbook(source)
        ws = wb.sheet_by_index(0)
        all_rows = [ws.row_values(i) for i in range(ws.nrows)]
        headers = [str(h).strip() for h in all_rows[0]]
        return all_rows[1:], headers

    def _read_xlsx(self, source: str):
        wb = openpyxl.load_workbook(source, read_only=True, data_only=True)
        ws = wb.active
        all_rows = list(ws.iter_rows(values_only=True))
        headers = [str(h).strip() if h else '' for h in all_rows[0]]
        return all_rows[1:], headers
