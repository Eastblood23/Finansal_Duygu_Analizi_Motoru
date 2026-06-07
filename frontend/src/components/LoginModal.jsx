import { useState, useContext } from 'react';
import { AuthContext } from '../context/AuthContext';
import { X } from 'lucide-react';

export default function LoginModal({ isOpen, onClose }) {
  const { login, register } = useContext(AuthContext);
  const [isLogin, setIsLogin] = useState(true);
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  if (!isOpen) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    
    let success = false;
    if (isLogin) {
      success = await login(email, password);
      if (!success) setError('E-posta veya şifre hatalı.');
    } else {
      success = await register(email, password, firstName, lastName);
      if (!success) setError('Kayıt başarısız. Bu e-posta kullanılıyor olabilir.');
    }

    if (success) {
      onClose();
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={e => e.stopPropagation()}>
        <button className="modal-close" onClick={onClose}><X size={24} /></button>
        <h2>{isLogin ? 'Giriş Yap' : 'Kayıt Ol'}</h2>
        
        {error && <div className="modal-error">{error}</div>}
        
        <form onSubmit={handleSubmit} className="modal-form">
          {!isLogin && (
            <>
              <div className="form-group">
                <label>İsim</label>
                <input 
                  type="text" 
                  value={firstName} 
                  onChange={e => setFirstName(e.target.value)} 
                  required={!isLogin} 
                />
              </div>
              <div className="form-group">
                <label>Soyisim</label>
                <input 
                  type="text" 
                  value={lastName} 
                  onChange={e => setLastName(e.target.value)} 
                  required={!isLogin} 
                />
              </div>
            </>
          )}
          <div className="form-group">
            <label>E-posta</label>
            <input 
              type="email" 
              value={email} 
              onChange={e => setEmail(e.target.value)} 
              required 
            />
          </div>
          <div className="form-group">
            <label>Şifre</label>
            <input 
              type="password" 
              value={password} 
              onChange={e => setPassword(e.target.value)} 
              required 
            />
          </div>
          <button type="submit" className="submit-btn">
            {isLogin ? 'Giriş Yap' : 'Kayıt Ol'}
          </button>
        </form>
        
        <p className="modal-toggle-text">
          {isLogin ? "Hesabınız yok mu? " : "Zaten hesabınız var mı? "}
          <span onClick={() => setIsLogin(!isLogin)}>
            {isLogin ? 'Kayıt Ol' : 'Giriş Yap'}
          </span>
        </p>
      </div>
    </div>
  );
}
