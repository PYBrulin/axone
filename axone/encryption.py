import logging
import os

import cryptography
import cryptography.fernet


def fallback_to_temp_key(key_path: str) -> str:
    """Fallback to a temporary key location if the specified key file does not exist."""
    logging.warning(f"Encryption key file {key_path} does not exist. Trying to use the temporary key location.")
    temp_key_path = os.path.join("/tmp/axone_filekey.key")
    if os.path.exists(temp_key_path):
        with open(temp_key_path) as f:
            key = f.read().strip()
        return key
    else:
        raise FileNotFoundError(
            f"Temporary encryption key file {temp_key_path} does not exist. Generating a new encryption key."
        )


def load_encryption_key(key_path: str) -> dict:
    """Load the encryption key from a file."""
    if os.path.exists(key_path):
        try:
            with open(key_path) as f:
                key = f.read().strip()
        except FileNotFoundError:
            key = fallback_to_temp_key(key_path)
    else:
        try:
            with open(key_path) as f:
                key = f.read().strip()
        except FileNotFoundError:
            key = fallback_to_temp_key(key_path)

    return key


def generate_encryption_key(key_path: str = None) -> dict:
    """Generate a random encryption key."""
    if key_path is None:
        key_path = os.path.join("/tmp/axone_filekey.key")
    if os.path.exists(key_path):
        with open(key_path) as f:
            existing_key = f.read().strip()
        if existing_key:
            return existing_key
        logging.warning(f"Encryption key file {key_path} is empty. Generating a new encryption key.")
    key = cryptography.fernet.Fernet.generate_key()
    with open(key_path, "wb") as filekey:
        filekey.write(key)
    return key.decode()


def encrypt_data(data: bytes, key: str) -> bytes:
    """Encrypt data using the provided key."""
    fernet = cryptography.fernet.Fernet(key.encode())
    encrypted_data = fernet.encrypt(data)
    logging.debug("Encrypted data: %s", encrypted_data)
    return encrypted_data


def decrypt_data(encrypted_data: bytes, key: str) -> bytes:
    """Decrypt data using the provided key."""
    fernet = cryptography.fernet.Fernet(key.encode())
    decrypted_data = fernet.decrypt(encrypted_data)
    logging.debug("Decrypted data: %s", decrypted_data)
    return decrypted_data


if __name__ == "__main__":
    import argparse

    argparser = argparse.ArgumentParser(description="Generate an encryption key for Axone.")
    argparser.add_argument(
        "-k",
        "--key-path",
        type=str,
        default=os.path.join("/tmp/axone_filekey.key"),
        help="Path to save the generated encryption key.",
    )
    argparser.add_argument(
        "-g", "--generate", action="store_true", help="Generate a new encryption key and save it to the specified path."
    )
    args = argparser.parse_args()

    if args.generate:
        # Generate the encryption key and save it to the specified path
        key = generate_encryption_key(args.key_path)
        print(f"Generated encryption key at {args.key_path}: {key}")
    else:
        raise ValueError("No action specified. Use --generate to generate a new encryption key.")
