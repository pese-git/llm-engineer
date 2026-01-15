class Workspace:
    def __init__(self):
        self.files = {}

    def store_code(self, filename: str, code: str):
        self.files[filename] = code
        return {"message": f"stored {filename}", "filename": filename, "chars": len(code)}

    def read_code(self, filename: str):
        return {"filename": filename, "code": self.files.get(filename, "")}
