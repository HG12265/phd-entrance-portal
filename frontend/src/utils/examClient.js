export function getExamClientId() {
  let clientId = localStorage.getItem('exam_client_id');
  if (!clientId) {
    // Generate simple standard UUID-like identifier
    clientId = 'client-' + Math.random().toString(36).substring(2, 15) + '-' + Math.random().toString(36).substring(2, 15);
    localStorage.setItem('exam_client_id', clientId);
  }
  return clientId;
}
