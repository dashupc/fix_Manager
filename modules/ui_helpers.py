from datetime import datetime


def make_treeview_sortable(tree, numeric_columns=None):
    """Enable clickable sorting on Treeview headers."""
    numeric_columns = set(numeric_columns or [])
    sort_states = {}

    def convert_value(value, column):
        text = str(value).strip()
        if not text:
            return (3, '')
        cleaned = text.replace('¥', '').replace(',', '')
        if column in numeric_columns:
            try:
                return (0, float(cleaned or 0))
            except ValueError:
                pass
        for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
            try:
                return (1, datetime.strptime(text, fmt).timestamp())
            except ValueError:
                continue
        return (2, text.lower())

    def sort_column(column):
        reverse = sort_states.get(column, False)
        data = []
        for item in tree.get_children(''):
            data.append((convert_value(tree.set(item, column), column), item))
        data.sort(reverse=reverse)
        for index, (_, item) in enumerate(data):
            tree.move(item, '', index)
        sort_states[column] = not reverse

    for column in tree['columns']:
        heading_info = tree.heading(column)
        text = heading_info.get('text', column)
        tree.heading(column, text=text, command=lambda c=column: sort_column(c))

