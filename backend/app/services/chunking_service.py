def chunk_code(files, chunk_size=1000):
    chunks = []

    for file in files:
        content = file["content"]

        for i in range(0, len(content), chunk_size):
            chunks.append({
                "path": file["path"],
                "chunk": content[i:i + chunk_size]
            })

    return chunks