/**
 * Tests for validation.ts — validateFile() helper and schema constants.
 *
 * Does NOT test zod schema internals directly (that would be testing zod itself).
 * Focuses on the public surface: validateFile() and the exported constants.
 */

import { describe, it, expect } from 'vitest'
import {
  validateFile,
  ALLOWED_MIME_TYPES,
  ALLOWED_EXTENSIONS,
  MAX_FILE_SIZE,
} from '../validation'

// ─── Helpers ──────────────────────────────────────────────────────────────────

function makeFile(name: string, size: number, type: string): File {
  // File constructor: File(parts, filename, options)
  // We pass an array with a buffer of `size` bytes so .size is exact.
  const blob = new Uint8Array(size)
  return new File([blob], name, { type })
}

// ─── Constants ────────────────────────────────────────────────────────────────

describe('Constants', () => {
  it('MAX_FILE_SIZE equals 50 MB in bytes', () => {
    /**Should be exactly 52,428,800 bytes (50 * 1024 * 1024) */
    expect(MAX_FILE_SIZE).toBe(50 * 1024 * 1024)
  })

  it('ALLOWED_MIME_TYPES includes all expected document and image types', () => {
    /**Should cover pdf, docx, xlsx, doc, xls, jpeg, png, zip */
    const expected = [
      'application/pdf',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      'application/msword',
      'application/vnd.ms-excel',
      'image/jpeg',
      'image/png',
      'application/zip',
    ]

    expected.forEach((mime) => {
      expect(ALLOWED_MIME_TYPES).toContain(mime as (typeof ALLOWED_MIME_TYPES)[number])
    })
  })

  it('ALLOWED_EXTENSIONS includes extensions for all allowed MIME types', () => {
    /**Should list the human-readable extensions shown in UI error messages */
    const expected = ['.pdf', '.docx', '.xlsx', '.doc', '.xls', '.png', '.zip']
    expected.forEach((ext) => {
      expect(ALLOWED_EXTENSIONS).toContain(ext)
    })
  })
})

// ─── validateFile — happy paths ───────────────────────────────────────────────

describe('validateFile — valid files', () => {
  it('returns null for a PDF within size limit', () => {
    /**Should accept a 1 MB PDF as valid */
    const file = makeFile('report.pdf', 1 * 1024 * 1024, 'application/pdf')
    expect(validateFile(file)).toBeNull()
  })

  it('returns null for a DOCX within size limit', () => {
    /**Should accept a Word document with the correct OOXML MIME type */
    const file = makeFile(
      'doc.docx',
      500 * 1024,
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    )
    expect(validateFile(file)).toBeNull()
  })

  it('returns null for a XLSX within size limit', () => {
    /**Should accept an Excel spreadsheet with the correct OOXML MIME type */
    const file = makeFile(
      'sheet.xlsx',
      200 * 1024,
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    expect(validateFile(file)).toBeNull()
  })

  it('returns null for a legacy DOC file', () => {
    /**Should accept the legacy Word MIME type (application/msword) */
    const file = makeFile('old.doc', 100 * 1024, 'application/msword')
    expect(validateFile(file)).toBeNull()
  })

  it('returns null for a legacy XLS file', () => {
    /**Should accept the legacy Excel MIME type (application/vnd.ms-excel) */
    const file = makeFile('old.xls', 100 * 1024, 'application/vnd.ms-excel')
    expect(validateFile(file)).toBeNull()
  })

  it('returns null for a JPEG image', () => {
    /**Should accept image/jpeg */
    const file = makeFile('photo.jpg', 2 * 1024 * 1024, 'image/jpeg')
    expect(validateFile(file)).toBeNull()
  })

  it('returns null for a PNG image', () => {
    /**Should accept image/png */
    const file = makeFile('screenshot.png', 3 * 1024 * 1024, 'image/png')
    expect(validateFile(file)).toBeNull()
  })

  it('returns null for a ZIP archive', () => {
    /**Should accept application/zip */
    const file = makeFile('archive.zip', 10 * 1024 * 1024, 'application/zip')
    expect(validateFile(file)).toBeNull()
  })

  it('returns null for a file at exactly the 50MB limit', () => {
    /**Boundary: a file of exactly MAX_FILE_SIZE bytes should be accepted */
    const file = makeFile('boundary.pdf', MAX_FILE_SIZE, 'application/pdf')
    expect(validateFile(file)).toBeNull()
  })
})

// ─── validateFile — size errors ───────────────────────────────────────────────

describe('validateFile — size violations', () => {
  it('returns an error message for a file 1 byte over 50MB', () => {
    /**Boundary: MAX_FILE_SIZE + 1 must be rejected */
    const file = makeFile('too-big.pdf', MAX_FILE_SIZE + 1, 'application/pdf')
    const result = validateFile(file)
    expect(result).not.toBeNull()
    expect(result).toContain('50')
  })

  it('error message for oversized file mentions the MB limit', () => {
    /**Should tell the user the maximum allowed size so they know why it failed */
    const file = makeFile('huge.pdf', 100 * 1024 * 1024, 'application/pdf')
    const result = validateFile(file)
    expect(result).toMatch(/50\s*MB/i)
  })

  it('a 51MB file with valid MIME type is rejected for size, not MIME', () => {
    /**Size check must run before MIME check so the user sees the size message */
    const file = makeFile('big.pdf', 51 * 1024 * 1024, 'application/pdf')
    const result = validateFile(file)
    expect(result).not.toBeNull()
    // Message must be about size, not about file type
    expect(result).not.toContain('Tipo de archivo no permitido')
  })
})

// ─── validateFile — MIME type errors ─────────────────────────────────────────

describe('validateFile — MIME type violations', () => {
  it('returns an error message for an MP4 video file', () => {
    /**Should reject video/mp4 as an unsupported type */
    const file = makeFile('movie.mp4', 1 * 1024 * 1024, 'video/mp4')
    const result = validateFile(file)
    expect(result).not.toBeNull()
    expect(result).toContain('Tipo de archivo no permitido')
  })

  it('returns an error message for a plain text file', () => {
    /**Should reject text/plain even though it could technically be opened */
    const file = makeFile('notes.txt', 1024, 'text/plain')
    const result = validateFile(file)
    expect(result).not.toBeNull()
    expect(result).toContain('Tipo de archivo no permitido')
  })

  it('returns an error message for an EXE file', () => {
    /**Should reject application/x-msdownload — security risk */
    const file = makeFile('setup.exe', 5 * 1024 * 1024, 'application/x-msdownload')
    const result = validateFile(file)
    expect(result).not.toBeNull()
    expect(result).toContain('Tipo de archivo no permitido')
  })

  it('error message for disallowed type lists accepted formats', () => {
    /**Should show the user what file types ARE accepted so they can resubmit */
    const file = makeFile('data.csv', 50 * 1024, 'text/csv')
    const result = validateFile(file)
    expect(result).toContain('.pdf')
  })

  it('rejects an empty MIME type string', () => {
    /**A file with no detected MIME type must be rejected, not silently accepted */
    const file = makeFile('unknown', 1024, '')
    const result = validateFile(file)
    expect(result).not.toBeNull()
  })
})
