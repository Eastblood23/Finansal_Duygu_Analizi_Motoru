import React, { useState, useContext } from 'react';
import { AuthContext } from '../context/AuthContext';
import { Wallet, X, Check, Trash2 } from 'lucide-react';

const PortfolioModal = ({ isOpen, onClose, symbol, assetName, currentPriceUsd, usdTryRate, defaultTab = 'amount' }) => {
  const { setPortfolioItem, portfolio, removeFromPortfolio } = useContext(AuthContext);
  
  // Find current amount
  const currentItem = portfolio.find(p => p.symbol === symbol);
  const currentAmount = currentItem ? currentItem.amount : 0;
  
  // Calculate asset price in TRY
  const getAssetPriceInTry = () => {
    if (symbol === 'USD_TRY' || symbol === 'USD/TRY') return currentPriceUsd;
    return currentPriceUsd * usdTryRate;
  };
  const priceInTry = getAssetPriceInTry();

  const getInitialValue = () => {
    if (!currentAmount) return 0;
    if (defaultTab === 'try') return (currentAmount * priceInTry).toFixed(2);
    if (defaultTab === 'gram') return (currentAmount * 31.1034768).toFixed(6);
    return currentAmount;
  }

  const [inputType, setInputType] = useState(defaultTab); // 'amount', 'try' or 'gram'
  const [inputValue, setInputValue] = useState(getInitialValue());
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  if (!isOpen) return null;

  const handleToggle = (type) => {
    if (type === inputType) return;
    
    let baseAmount = parseFloat(inputValue || 0);
    if (inputType === 'try') {
      baseAmount = baseAmount / priceInTry;
    } else if (inputType === 'gram') {
      baseAmount = baseAmount / 31.1034768;
    }

    if (type === 'try') {
      setInputValue((baseAmount * priceInTry).toFixed(2));
    } else if (type === 'gram') {
      setInputValue((baseAmount * 31.1034768).toFixed(6));
    } else {
      setInputValue(baseAmount.toFixed(6));
    }
    setInputType(type);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    
    let finalAmount = parseFloat(inputValue);
    if (!Number.isFinite(finalAmount) || finalAmount < 0 || (inputType === 'try' && !(priceInTry > 0))) {
      setError('Geçerli bir miktar ve dönüşüm için güncel fiyat gereklidir.');
      return;
    }
    if (inputType === 'try') {
      finalAmount = finalAmount / priceInTry;
    } else if (inputType === 'gram') {
      finalAmount = finalAmount / 31.1034768;
    }
    
    if (!Number.isFinite(finalAmount)) {
      setError('Miktar hesaplanamadı.');
      return;
    }
    setLoading(true);
    const saved = await setPortfolioItem(symbol, finalAmount);
    setLoading(false);
    if (saved) onClose();
    else setError('Portföy kaydedilemedi. Lütfen tekrar deneyin.');
  };

  return (
    <div className="modal-overlay">
      <div className="modal-content glass-panel" style={{ maxWidth: '400px' }}>
        <button className="modal-close" onClick={onClose}><X size={24} color="#94a3b8" /></button>
        
        <h2 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1.5rem', color: '#fff' }}>
          <Wallet size={24} color="#60a5fa" />
          Portföye Ekle
        </h2>
        <p style={{ color: '#94a3b8', marginBottom: '1.5rem' }}>
          Cüzdanınızdaki <strong>{assetName}</strong> ({symbol}) miktarını giriniz.
        </p>
        {symbol === 'GOLD' && <p style={{ color: '#94a3b8', fontSize: '0.85rem' }}>Altın değeri vadeli kontrat fiyatıyla yaklaşık hesaplanır; fiziki altın alış/satış fiyatı değildir.</p>}
        {error && <p role="alert" style={{ color: '#f87171' }}>{error}</p>}

        <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem' }}>
          <button 
            type="button"
            onClick={() => handleToggle('amount')}
            style={{ 
              flex: 1, padding: '0.5rem', borderRadius: '4px', cursor: 'pointer',
              background: inputType === 'amount' ? 'rgba(96, 165, 250, 0.2)' : 'transparent',
              border: inputType === 'amount' ? '1px solid #60a5fa' : '1px solid rgba(255,255,255,0.1)',
              color: inputType === 'amount' ? '#60a5fa' : '#94a3b8'
            }}
          >
            {symbol === 'GOLD' ? 'Troy Ons' : symbol === 'USD_TRY' ? 'USD Miktarı' : 'BTC Miktarı'}
          </button>
          {symbol === 'GOLD' && (
            <button 
              type="button"
              onClick={() => handleToggle('gram')}
              style={{ 
                flex: 1, padding: '0.5rem', borderRadius: '4px', cursor: 'pointer',
                background: inputType === 'gram' ? 'rgba(251, 191, 36, 0.2)' : 'transparent',
                border: inputType === 'gram' ? '1px solid #fbbf24' : '1px solid rgba(255,255,255,0.1)',
                color: inputType === 'gram' ? '#fbbf24' : '#94a3b8'
              }}
            >
              Adet / Gram
            </button>
          )}
          <button 
            type="button"
            onClick={() => handleToggle('try')}
            style={{ 
              flex: 1, padding: '0.5rem', borderRadius: '4px', cursor: 'pointer',
              background: inputType === 'try' ? 'rgba(74, 222, 128, 0.2)' : 'transparent',
              border: inputType === 'try' ? '1px solid #4ade80' : '1px solid rgba(255,255,255,0.1)',
              color: inputType === 'try' ? '#4ade80' : '#94a3b8'
            }}
          >
            TL Karşılığı
          </button>
        </div>

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div className="input-group">
            <label style={{ color: '#e2e8f0', fontSize: '0.9rem' }}>
              {inputType === 'amount' ? 'Miktar' : inputType === 'gram' ? 'Gram Miktarı' : 'TL Değeri (₺)'}
            </label>
            <input 
              type="number" 
              step="any"
              min="0"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              className="glass-input"
              style={{ padding: '0.75rem', marginTop: '0.5rem', width: '100%' }}
              required 
            />
            {inputType === 'try' && priceInTry && (
               <small style={{ display: 'block', marginTop: '0.5rem', color: '#94a3b8' }}>
                 Tahmini Adet: {(parseFloat(inputValue || 0) / priceInTry).toFixed(6)} {symbol}
               </small>
            )}
          </div>

          <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1rem' }}>
            {currentAmount > 0 && (
              <button 
                type="button"
                onClick={async () => {
                  setLoading(true);
                  await removeFromPortfolio(symbol);
                  setLoading(false);
                  onClose();
                }}
                disabled={loading}
                title="Portföyden Çıkar"
                style={{ flex: '0 0 auto', padding: '0.75rem', borderRadius: '8px', background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.2)', color: '#ef4444', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', transition: 'all 0.2s' }}
                onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(239, 68, 68, 0.2)'; e.currentTarget.style.transform = 'scale(1.05)' }}
                onMouseLeave={(e) => { e.currentTarget.style.background = 'rgba(239, 68, 68, 0.1)'; e.currentTarget.style.transform = 'scale(1)' }}
              >
                <Trash2 size={20} />
              </button>
            )}
            <button 
              type="submit" 
              className="auth-button" 
              disabled={loading}
              style={{ flex: 1, display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '0.5rem' }}
            >
              {loading ? <div className="spinner" style={{ width: '20px', height: '20px' }}></div> : <Check size={20} />}
              {loading ? 'Güncelleniyor...' : 'Bakiyeyi Kaydet'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default PortfolioModal;
