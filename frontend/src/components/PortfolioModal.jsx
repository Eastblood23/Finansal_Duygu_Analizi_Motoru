import React, { useState, useContext, useRef } from 'react';
import { AuthContext } from '../context/AuthContext';
import { Wallet, X, Check, Trash2 } from 'lucide-react';

const GRAMS_PER_OUNCE = 31.1034768;

const PortfolioModal = ({ isOpen, onClose, symbol, assetName, currentPrice, usdTryRate, defaultTab = 'amount' }) => {
  const { setPortfolioItem, portfolio, removeFromPortfolio } = useContext(AuthContext);
  const currentItem = portfolio.find(p => p.symbol === symbol);
  const currentAmount = currentItem?.amount || 0;
  const priceInTry = ['USD_TRY', 'EUR_TRY'].includes(symbol) ? currentPrice : currentPrice * usdTryRate;
  const canConvert = Number.isFinite(priceInTry) && priceInTry > 0;
  const initialType = defaultTab === 'try' && canConvert ? 'try' : 'amount';
  const [inputType, setInputType] = useState(initialType);
  const [inputValue, setInputValue] = useState(String(initialType === 'try' ? currentAmount * priceInTry : currentAmount));
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const busy = useRef(false);
  const amountLabel = { GOLD: 'Troy Ons', USD_TRY: 'USD Miktarı', EUR_TRY: 'EUR Miktarı', BTC: 'BTC Miktarı' }[symbol] || 'Miktar';
  if (!isOpen) return null;
  const toAmount = (value, type) => type === 'try' ? value / priceInTry : type === 'gram' ? value / GRAMS_PER_OUNCE : value;
  const toggle = type => {
    if (busy.current || type === inputType || (type === 'try' && !canConvert)) return;
    const amount = toAmount(Number(inputValue), inputType);
    if (!Number.isFinite(amount) || amount < 0) return;
    setInputValue(String(type === 'try' ? amount * priceInTry : type === 'gram' ? amount * GRAMS_PER_OUNCE : amount));
    setInputType(type);
    setError('');
  };
  const save = async (remove = false) => {
    if (busy.current) return;
    const amount = toAmount(Number(inputValue), inputType);
    if (!remove && (!inputValue.trim() || !Number.isFinite(amount) || amount < 0 || amount > 1e15 || (inputType === 'try' && !canConvert))) {
      setError('Geçerli bir miktar girin. TL dönüşümü için güncel fiyat gereklidir.');
      return;
    }
    busy.current = true;
    setLoading(true);
    setError('');
    try {
      const saved = remove ? await removeFromPortfolio(symbol) : await setPortfolioItem(symbol, amount);
      if (saved) onClose();
      else setError('İşlem tamamlanamadı. Lütfen tekrar deneyin.');
    } catch {
      setError('İşlem tamamlanamadı. Lütfen tekrar deneyin.');
    } finally {
      busy.current = false;
      setLoading(false);
    }
  };
  const tab = (type, label, disabled = false) => (
    <button type="button" disabled={loading || disabled} onClick={() => toggle(type)} aria-pressed={inputType === type}
      style={{ flex: 1, padding: '0.6rem', borderRadius: '6px', cursor: disabled ? 'not-allowed' : 'pointer', opacity: disabled ? 0.5 : 1,
        background: inputType === type ? 'rgba(96,165,250,0.2)' : 'transparent', border: '1px solid rgba(255,255,255,0.15)', color: inputType === type ? '#60a5fa' : '#94a3b8' }}>{label}</button>
  );
  return (
    <div className="modal-overlay">
      <div className="modal-content glass-panel" role="dialog" aria-modal="true" aria-labelledby="portfolio-modal-title" style={{ maxWidth: '400px' }}>
        <button className="modal-close" disabled={loading} onClick={onClose} aria-label="Kapat"><X size={24} color="#94a3b8" /></button>
        <h2 id="portfolio-modal-title" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem', color: '#fff' }}><Wallet size={24} color="#60a5fa" />{currentItem ? 'Varlığı Düzenle' : 'Portföye Ekle'}</h2>
        <p style={{ color: '#94a3b8', marginBottom: '1rem' }}><strong>{assetName}</strong> için toplam miktarınızı girin. Kaydettiğiniz miktar önceki bakiyenin yerini alır.</p>
        {symbol === 'GOLD' && <p style={{ color: '#94a3b8', fontSize: '0.85rem' }}>Altın değeri vadeli kontrat fiyatıyla yaklaşık hesaplanır; fiziki altın alış/satış fiyatı değildir.</p>}
        {!canConvert && <p style={{ color: '#94a3b8', fontSize: '0.85rem' }}>Güncel fiyat alınamadığı için TL dönüşümü kapalıdır. Miktarı düzenleyebilirsiniz.</p>}
        {error && <p role="alert" style={{ color: '#f87171' }}>{error}</p>}
        <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem' }}>{tab('amount', amountLabel)}{symbol === 'GOLD' && tab('gram', 'Gram')}{tab('try', 'TL Karşılığı', !canConvert)}</div>
        <form onSubmit={e => { e.preventDefault(); save(); }} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div className="input-group">
            <label htmlFor="portfolio-amount" style={{ color: '#e2e8f0', fontSize: '0.9rem' }}>{inputType === 'try' ? 'TL Değeri (₺)' : inputType === 'gram' ? 'Gram Miktarı' : amountLabel}</label>
            <input id="portfolio-amount" type="number" step="any" min="0" required disabled={loading} value={inputValue} onChange={e => setInputValue(e.target.value)} className="glass-input" style={{ padding: '0.75rem', marginTop: '0.5rem', width: '100%' }} />
          </div>
          <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1rem' }}>
            {currentItem && <button type="button" disabled={loading} onClick={() => save(true)} aria-label="Varlığı portföyden sil" style={{ padding: '0.75rem', borderRadius: '8px', background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.2)', color: '#ef4444', cursor: 'pointer' }}><Trash2 size={20} /></button>}
            <button type="submit" className="auth-button" disabled={loading} style={{ flex: 1, display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '0.5rem' }}><Check size={20} />{loading ? 'Kaydediliyor...' : 'Bakiyeyi Kaydet'}</button>
          </div>
        </form>
      </div>
    </div>
  );
};
export default PortfolioModal;
