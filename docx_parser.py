from docx import Document


DOCUMENT_PATH = "prepri.docx"


def find_explanation(word: str):

    document = Document(DOCUMENT_PATH)

    paragraphs = [
        paragraph.text.strip()
        for paragraph in document.paragraphs
        if paragraph.text.strip()
    ]

    word = word.lower().strip()

    start_index = None

    # Ищем карточку по строке "Правильно"
    for i, paragraph in enumerate(paragraphs):

        if "Правильно:" in paragraph:

            correct_word = (
                paragraph
                .split("Правильно:", 1)[1]
                .strip()
                .strip("*")
                .strip()
            )

            if correct_word.lower() == word:
                start_index = i - 1
                break

    if start_index is None:
        return None

    # Ищем начало следующей карточки
    end_index = len(paragraphs)

    for i in range(start_index + 1, len(paragraphs)):

        if paragraphs[i].startswith("❌ Неверно:"):
            end_index = i
            break

    card = "\n\n".join(
        paragraphs[start_index:end_index]
    )

    return card

if __name__ == "__main__":

    result = find_explanation("преамбула")

    if result:
        print(result)
    else:
        print("Объяснение не найдено.")
