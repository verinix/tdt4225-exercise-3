from pathlib import Path
import kagglehub

DATA_PATH = Path(__file__).parent / "data"

def main():
    path = kagglehub.dataset_download(
        "rounakbanik/the-movies-dataset",
        output_dir=str(DATA_PATH)
    )
    print(f"Dataset downloaded to: {path}")

if __name__ == "__main__":
    main()
