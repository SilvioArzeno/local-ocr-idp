import axios from 'axios'

export async function extractDocument({ file, prompts, documentType }) {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('prompts', JSON.stringify(prompts))
  formData.append('document_type', documentType)

  const response = await axios.post('/api/extract', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return response.data
}
