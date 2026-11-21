/**
 * @file crypto.js
 * @description Web Crypto API implementation for AES-256-GCM token encryption and decryption.
 * Matches Python's crypto_engine.py: salt(16) + nonce(12) + ciphertext(N with tag).
 */

class CryptoEngine {
  /**
   * Salt length in bytes for PBKDF2 key derivation.
   * @type {number}
   */
  static SALT_SIZE = 16;

  /**
   * Nonce / IV length in bytes for AES-GCM.
   * @type {number}
   */
  static NONCE_SIZE = 12;

  /**
   * PBKDF2 iteration count.
   * @type {number}
   */
  static ITERATIONS = 100000;

  /**
   * Derive a 256-bit AES-GCM CryptoKey from a passphrase and salt using PBKDF2 with SHA-256.
   *
   * @param {string} password - User passphrase.
   * @param {Uint8Array} salt - 16-byte random salt.
   * @returns {Promise<CryptoKey>} Derived AES-GCM key suitable for encryption and decryption.
   */
  static async deriveKey(password, salt) {
    if (!password || typeof password !== 'string') {
      throw new Error('Password must be a non-empty string.');
    }
    if (!(salt instanceof Uint8Array) || salt.byteLength !== CryptoEngine.SALT_SIZE) {
      throw new Error(`Salt must be a Uint8Array of ${CryptoEngine.SALT_SIZE} bytes.`);
    }

    const encoder = new TextEncoder();
    const encodedPassword = encoder.encode(password);

    // Import the raw password bytes as a PBKDF2 base key
    const baseKey = await crypto.subtle.importKey(
      'raw',
      encodedPassword,
      { name: 'PBKDF2' },
      false,
      ['deriveKey']
    );

    // Derive the AES-GCM 256-bit key
    const derivedKey = await crypto.subtle.deriveKey(
      {
        name: 'PBKDF2',
        salt: salt,
        iterations: CryptoEngine.ITERATIONS,
        hash: 'SHA-256'
      },
      baseKey,
      {
        name: 'AES-GCM',
        length: 256
      },
      false,
      ['encrypt', 'decrypt']
    );

    return derivedKey;
  }

  /**
   * Decrypt an encrypted base64 sync token using AES-256-GCM.
   * Format: base64(salt[16] + nonce[12] + ciphertext_with_tag[N])
   *
   * @param {string} base64Token - Base64 encoded encrypted token.
   * @param {string} password - Decryption passphrase.
   * @returns {Promise<{memory: Object, api_configs: Array<Object>}>} Decrypted payload object.
   */
  static async decrypt(base64Token, password) {
    if (!base64Token || typeof base64Token !== 'string') {
      throw new Error('Sync token is required and must be a string.');
    }
    if (!password || typeof password !== 'string') {
      throw new Error('Passphrase is required.');
    }

    // Clean whitespace and normalize base64
    const cleanToken = base64Token.trim().replace(/\s+/g, '');
    let rawBytes;
    try {
      rawBytes = CryptoEngine.base64ToUint8Array(cleanToken);
    } catch (err) {
      throw new Error('Invalid Base64 encoding in sync token.');
    }

    // Minimum length: 16 (salt) + 12 (nonce) + 16 (GCM auth tag) = 44 bytes
    const minLength = CryptoEngine.SALT_SIZE + CryptoEngine.NONCE_SIZE + 16;
    if (rawBytes.byteLength < minLength) {
      throw new Error(`Token is too short (${rawBytes.byteLength} bytes). Minimum required is ${minLength} bytes.`);
    }

    // Extract salt, nonce, and ciphertext (with authentication tag)
    const salt = rawBytes.slice(0, CryptoEngine.SALT_SIZE);
    const nonce = rawBytes.slice(
      CryptoEngine.SALT_SIZE,
      CryptoEngine.SALT_SIZE + CryptoEngine.NONCE_SIZE
    );
    const ciphertextWithTag = rawBytes.slice(
      CryptoEngine.SALT_SIZE + CryptoEngine.NONCE_SIZE
    );

    // Derive AES-GCM key
    const key = await CryptoEngine.deriveKey(password, salt);

    // Decrypt using Web Crypto API
    let decryptedBuffer;
    try {
      decryptedBuffer = await crypto.subtle.decrypt(
        {
          name: 'AES-GCM',
          iv: nonce,
          tagLength: 128
        },
        key,
        ciphertextWithTag
      );
    } catch (err) {
      throw new Error('Decryption failed. Invalid passphrase or corrupted token.');
    }

    // Decode decrypted bytes into JSON string
    const decoder = new TextDecoder('utf-8');
    const jsonString = decoder.decode(decryptedBuffer);

    let parsedPayload;
    try {
      parsedPayload = JSON.parse(jsonString);
    } catch (err) {
      throw new Error('Decrypted payload is not valid JSON.');
    }

    return parsedPayload;
  }

  /**
   * Encrypt an arbitrary data object or string into a base64 sync token.
   * Format: base64(salt[16] + nonce[12] + ciphertext_with_tag[N])
   *
   * @param {Object|string} data - Payload to encrypt.
   * @param {string} password - Encryption passphrase.
   * @returns {Promise<string>} Base64 encoded encrypted token.
   */
  static async encrypt(data, password) {
    if (data === undefined || data === null) {
      throw new Error('Data to encrypt cannot be null or undefined.');
    }
    if (!password || typeof password !== 'string') {
      throw new Error('Passphrase is required for encryption.');
    }

    const jsonString = typeof data === 'string' ? data : JSON.stringify(data);
    const encoder = new TextEncoder();
    const plaintextBytes = encoder.encode(jsonString);

    // Generate cryptographically secure random salt and nonce
    const salt = new Uint8Array(CryptoEngine.SALT_SIZE);
    crypto.getRandomValues(salt);

    const nonce = new Uint8Array(CryptoEngine.NONCE_SIZE);
    crypto.getRandomValues(nonce);

    // Derive key
    const key = await CryptoEngine.deriveKey(password, salt);

    // Encrypt with AES-GCM (automatically appends 16-byte auth tag)
    const encryptedBuffer = await crypto.subtle.encrypt(
      {
        name: 'AES-GCM',
        iv: nonce,
        tagLength: 128
      },
      key,
      plaintextBytes
    );

    const ciphertext = new Uint8Array(encryptedBuffer);

    // Concatenate salt + nonce + ciphertext
    const combinedLength = salt.byteLength + nonce.byteLength + ciphertext.byteLength;
    const combinedBytes = new Uint8Array(combinedLength);

    combinedBytes.set(salt, 0);
    combinedBytes.set(nonce, salt.byteLength);
    combinedBytes.set(ciphertext, salt.byteLength + nonce.byteLength);

    return CryptoEngine.uint8ArrayToBase64(combinedBytes);
  }

  /**
   * Convert a Uint8Array to a Base64 string safely without stack overflow.
   *
   * @param {Uint8Array} bytes - Bytes to encode.
   * @returns {string} Base64 string.
   */
  static uint8ArrayToBase64(bytes) {
    const CHUNK_SIZE = 0x8000; // 32KB chunks
    const chunks = [];
    for (let i = 0; i < bytes.length; i += CHUNK_SIZE) {
      const subarray = bytes.subarray(i, Math.min(i + CHUNK_SIZE, bytes.length));
      chunks.push(String.fromCharCode.apply(null, subarray));
    }
    return btoa(chunks.join(''));
  }

  /**
   * Convert a Base64 string to a Uint8Array.
   * Supports standard Base64 and URL-safe Base64.
   *
   * @param {string} base64Str - Base64 string.
   * @returns {Uint8Array} Decoded byte array.
   */
  static base64ToUint8Array(base64Str) {
    // Replace URL-safe characters and add padding if missing
    let normalized = base64Str.replace(/-/g, '+').replace(/_/g, '/');
    while (normalized.length % 4 !== 0) {
      normalized += '=';
    }

    const binaryString = atob(normalized);
    const len = binaryString.length;
    const bytes = new Uint8Array(len);
    for (let i = 0; i < len; i++) {
      bytes[i] = binaryString.charCodeAt(i);
    }
    return bytes;
  }
}

// Make accessible to both browser window and module systems if required
if (typeof window !== 'undefined') {
  window.CryptoEngine = CryptoEngine;
}
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { CryptoEngine };
}
