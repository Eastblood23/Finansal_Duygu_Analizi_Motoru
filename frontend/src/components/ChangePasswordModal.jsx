import { useContext, useState } from 'react';
import { X } from 'lucide-react';
import { AuthContext } from '../context/AuthContext';

export default function ChangePasswordModal({ onClose, onSuccess }) {
  const { user, changePassword } = useContext(AuthContext);
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [error, setError] = useState('');
  const [pending, setPending] = useState(false);

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (pending) return;
    setError('');
    if (newPassword !== confirmation) {
      setError('Yeni şifreler eşleşmiyor.');
      return;
    }
    if (newPassword === currentPassword) {
      setError('Yeni şifre mevcut şifreden farklı olmalı.');
      return;
    }
    if ([...newPassword].length < 15 || [...newPassword].length > 128) {
      setError('Yeni şifre 15–128 karakter olmalı.');
      return;
    }
    setPending(true);
    const result = await changePassword(currentPassword, newPassword);
    setPending(false);
    if (result.ok) {
      setCurrentPassword('');
      setNewPassword('');
      setConfirmation('');
      onSuccess();
    } else {
      setError(result.error);
    }
  };

  return (
    <div className="modal-overlay" onClick={() => !pending && onClose()}>
      <div className="modal-content" role="dialog" aria-modal="true" aria-labelledby="change-password-title" onClick={event => event.stopPropagation()}>
        <button type="button" className="modal-close" aria-label="Kapat" disabled={pending} onClick={onClose}><X size={24} /></button>
        <h2 id="change-password-title">Şifre Değiştir</h2>
        <p className="password-help">Yalnızca bu uygulamada kullandığınız, en az 15 karakterlik bir şifre seçin. Değişiklikten sonra tüm oturumlarınız kapanır.</p>
        {error && <div className="modal-error" role="alert">{error}</div>}
        <form onSubmit={handleSubmit} className="modal-form">
          <div className="form-group">
            <label htmlFor="change-password-email">E-posta</label>
            <input id="change-password-email" name="username" type="email" autoComplete="username" value={user?.email || ''} readOnly />
          </div>
          <div className="form-group">
            <label htmlFor="current-password">Mevcut şifre</label>
            <input id="current-password" name="current_password" type="password" autoComplete="current-password" value={currentPassword} onChange={event => setCurrentPassword(event.target.value)} maxLength={1024} required disabled={pending} />
          </div>
          <div className="form-group">
            <label htmlFor="new-password">Yeni şifre</label>
            <input id="new-password" name="new_password" type="password" autoComplete="new-password" value={newPassword} onChange={event => setNewPassword(event.target.value)} minLength={15} maxLength={128} required disabled={pending} />
          </div>
          <div className="form-group">
            <label htmlFor="confirm-password">Yeni şifre (tekrar)</label>
            <input id="confirm-password" name="confirm_password" type="password" autoComplete="new-password" value={confirmation} onChange={event => setConfirmation(event.target.value)} minLength={15} maxLength={128} required disabled={pending} />
          </div>
          <button className="submit-btn" type="submit" disabled={pending}>{pending ? 'Kaydediliyor…' : 'Şifreyi Değiştir'}</button>
        </form>
      </div>
    </div>
  );
}
