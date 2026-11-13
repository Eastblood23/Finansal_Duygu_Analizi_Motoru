import { useState, useContext, useEffect, useRef } from 'react';
import { AuthContext } from '../context/AuthContext';
import { X } from 'lucide-react';

export default function LoginModal({ isOpen, onClose }) {
  const { login, register, verifyRegistration } = useContext(AuthContext);
  const [isLogin, setIsLogin] = useState(true);
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [challenge, setChallenge] = useState(null);
  const [code, setCode] = useState('');
  const [busy, setBusy] = useState(false);
  const generation = useRef(0);

  useEffect(() => {
    generation.current += 1;
    setPassword('');
    setError('');
    setChallenge(null);
    setCode('');
    setBusy(false);
  }, [isOpen, isLogin]);

  if (!isOpen) return null;

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (busy) return;
    const current = generation.current;
    setBusy(true);
    setError('');
    try {
      if (challenge) {
        const result = await verifyRegistration(challenge.challenge_id, code);
        if (current !== generation.current) return;
        if (result.ok) onClose();
        else setError(result.error);
      } else if (isLogin) {
        const success = await login(email, password);
        if (current !== generation.current) return;
        if (success) onClose();
        else setError('Giriş yapılamadı. Bilgilerinizi ve bağlantınızı kontrol edin.');
      } else {
        const result = await register(email, password, firstName, lastName);
        if (current !== generation.current) return;
        if (result.ok) {
          setChallenge(result);
          setPassword('');
        } else setError(result.error);
      }
    } finally {
      if (current === generation.current) setBusy(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={busy ? undefined : onClose}>
      <div className="modal-content" role="dialog" aria-modal="true" aria-labelledby="auth-title" onClick={e => e.stopPropagation()}>
        <button className="modal-close" onClick={onClose} disabled={busy} aria-label="Kapat"><X size={24} /></button>
        <h2 id="auth-title">{challenge ? 'E-postanı Doğrula' : isLogin ? 'Giriş Yap' : 'Kayıt Ol'}</h2>
        {error && <div className="modal-error" role="alert">{error}</div>}
        <form onSubmit={handleSubmit} className="modal-form" aria-busy={busy}>
          {challenge ? (
            <>
              <p>{email} adresine gönderilen 6 haneli kodu girin. Kod 10 dakika geçerli, deneme hakkınız 5. Spam klasörünü de kontrol edin.</p>
              <div className="form-group">
                <label htmlFor="auth-code">Doğrulama kodu</label>
                <input id="auth-code" name="one-time-code" type="text" inputMode="numeric" autoComplete="one-time-code"
                  pattern="[0-9]{6}" maxLength={6} value={code} disabled={busy} required autoFocus
                  onChange={e => setCode(e.target.value.replace(/\D/g, ''))} />
              </div>
            </>
          ) : (
            <>
              {!isLogin && (
                <>
                  <div className="form-group">
                    <label htmlFor="auth-first-name">İsim</label>
                    <input type="text" id="auth-first-name" name="given-name" autoComplete="given-name" maxLength={100}
                      value={firstName} onChange={e => setFirstName(e.target.value)} disabled={busy} required />
                  </div>
                  <div className="form-group">
                    <label htmlFor="auth-last-name">Soyisim</label>
                    <input type="text" id="auth-last-name" name="family-name" autoComplete="family-name" maxLength={100}
                      value={lastName} onChange={e => setLastName(e.target.value)} disabled={busy} required />
                  </div>
                </>
              )}
              <div className="form-group">
                <label htmlFor="auth-email">E-posta</label>
                <input type="email" id="auth-email" name="username" autoComplete="username" maxLength={254}
                  value={email} onChange={e => setEmail(e.target.value)} disabled={busy} required />
              </div>
              <div className="form-group">
                <label htmlFor="auth-password">Şifre</label>
                <input type="password" id="auth-password" name="password" autoComplete={isLogin ? 'current-password' : 'new-password'}
                  minLength={isLogin ? undefined : 15} maxLength={isLogin ? 1024 : 128} value={password}
                  onChange={e => setPassword(e.target.value)} disabled={busy} required />
                {!isLogin && <small>Yalnızca bu uygulamada kullandığınız, en az 15 karakterlik bir şifre seçin.</small>}
              </div>
            </>
          )}
          <button type="submit" className="submit-btn" disabled={busy}>
            {busy ? 'İşleniyor…' : challenge ? 'Doğrula ve Hesabı Aç' : isLogin ? 'Giriş Yap' : 'Doğrulama Kodu Gönder'}
          </button>
          {challenge && (
            <button type="button" className="submit-btn" disabled={busy} onClick={() => {
              setChallenge(null); setCode(''); setError('');
            }}>Kod gelmedi mi? 60 saniye sonra yeniden kayıt başlat</button>
          )}
        </form>
        <p className="modal-toggle-text">
          {isLogin ? 'Hesabınız yok mu? ' : 'Zaten hesabınız var mı? '}
          <button type="button" disabled={busy} onClick={() => setIsLogin(!isLogin)}>
            {isLogin ? 'Kayıt Ol' : 'Giriş Yap'}
          </button>
        </p>
      </div>
    </div>
  );
}
