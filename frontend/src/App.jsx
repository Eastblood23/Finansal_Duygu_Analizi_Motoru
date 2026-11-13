import { useState, useEffect, useContext } from 'react'
import { Activity, TrendingUp, TrendingDown, Minus, RefreshCw, DollarSign, Euro, Coins, Gem, LineChart, Filter, User, LogOut, Bookmark, BookmarkCheck, Bitcoin, Wallet, Plus, ShieldAlert, Edit2, Trash2 } from 'lucide-react'
import { LineChart as RechartsLineChart, Line, ResponsiveContainer, YAxis } from 'recharts'
import { AuthProvider, AuthContext } from './context/AuthContext'
import LoginModal from './components/LoginModal'
import ChangePasswordModal from './components/ChangePasswordModal'
import CorrelationChart from './components/CorrelationChart'
import ChatbotWidget from './components/ChatbotWidget'
import PortfolioModal from './components/PortfolioModal'

function Dashboard() {
  const { user, watchlists, logout, addToWatchlist, removeFromWatchlist } = useContext(AuthContext)

  const [news, setNews] = useState([])
  const [market, setMarket] = useState(null)
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState(null)
  const [isLoginModalOpen, setIsLoginModalOpen] = useState(false)
  const [isPasswordModalOpen, setIsPasswordModalOpen] = useState(false)
  const [authNotice, setAuthNotice] = useState('')
  const [portfolioModalData, setPortfolioModalData] = useState(null)
  const { portfolioReport, portfolio, removeFromPortfolio } = useContext(AuthContext)

  // Filters and Pagination
  const [offset, setOffset] = useState(0)
  const [assetFilter, setAssetFilter] = useState("")
  const [sentimentFilter, setSentimentFilter] = useState("")
  const [showWatchlistOnly, setShowWatchlistOnly] = useState(false)
  const [hasMore, setHasMore] = useState(true)

  useEffect(() => {
    if (user) setAuthNotice('')
  }, [user])

  const fetchData = async (isLoadMore = false) => {
    if (isLoadMore) setLoadingMore(true)
    else setLoading(true)

    setError(null)
    try {
      const currentOffset = isLoadMore ? offset + 50 : 0
      if (!isLoadMore) setOffset(0)

      let newsUrl = `/api/sentiment/latest?limit=50&offset=${currentOffset}`
      if (isLoadMore && news.length > 0) {
        const last = news[news.length - 1];
        if (last.published_at && last.id) {
          newsUrl = `/api/sentiment/latest?limit=50&before_time=${encodeURIComponent(last.published_at)}&before_id=${last.id}`;
        }
      }
      if (assetFilter) newsUrl += `&asset_type=${assetFilter}`
      if (sentimentFilter) newsUrl += `&sentiment_label=${sentimentFilter}`

      const promises = [fetch(newsUrl)]
      if (!isLoadMore) promises.push(fetch('/api/market/ticker'))

      const responses = await Promise.all(promises)
      const newsRes = responses[0]
      if (!newsRes.ok) throw new Error('Haber ağ hatası: ' + newsRes.status)

      const newsData = await newsRes.json()

      if (newsData.length < 50) setHasMore(false)
      else setHasMore(true)

      let finalNews = newsData;
      // Eğer "Sadece Takip Ettiklerim" seçiliyse, frontend'de filtrele
      if (showWatchlistOnly && user && watchlists.length > 0) {
         const trackedAssets = watchlists.map(w => w.asset_type);

         const impliedCategories = new Set(trackedAssets);
         if (trackedAssets.includes("GOLD") || trackedAssets.includes("BIST100") || trackedAssets.includes("USD_TRY") || trackedAssets.includes("EUR_TRY")) {
            impliedCategories.add("GENERAL");
         }
         if (trackedAssets.includes("BTC")) {
            impliedCategories.add("CRYPTO");
         }

         finalNews = newsData.filter(item => impliedCategories.has(item.asset_type));
      } else if (showWatchlistOnly && user && watchlists.length === 0) {
         finalNews = []; // Takip listesi boşsa hiç haber gösterme
      }

      if (isLoadMore) {
        setNews(prev => {
          // Gelen verideki id'ler prev içinde var mı kontrol et, yoksa ekle (duplicate önlemi)
          const existingIds = new Set(prev.map(item => item.id));
          const newItems = finalNews.filter(item => !existingIds.has(item.id));
          return [...prev, ...newItems];
        })
        setOffset(currentOffset)
      } else {
        setNews(finalNews)
        if (responses.length > 1) {
          const marketRes = responses[1]
          if (!marketRes.ok) throw new Error('Piyasa ağ hatası: ' + marketRes.status)
          const marketData = await marketRes.json()

          // Calculate Gram Gold dynamically
          if (marketData?.GOLD?.price > 0 && marketData?.USD_TRY?.price > 0) {
            const goldOunce = marketData.GOLD.price;
            const usdTry = marketData.USD_TRY.price;
            const gramGold = (goldOunce / 31.1034768) * usdTry;

            const goldPrev = marketData.GOLD.prev_close;
            const usdPrev = marketData.USD_TRY.prev_close;
            const gramPrev = goldPrev > 0 && usdPrev > 0 ? (goldPrev / 31.1034768) * usdPrev : null;
            const gramChange = gramPrev != null ? gramGold - gramPrev : null;
            const gramChangePct = gramPrev > 0 ? (gramChange / gramPrev) * 100 : null;

            marketData.GRAM_GOLD = {
              price: gramGold,
              prev_close: gramPrev,
              change: gramChange,
              change_pct: gramChangePct,
              is_up: gramChange != null ? gramChange >= 0 : null,
              history: marketData.GOLD.history ? marketData.GOLD.history.map(h => ({
                ...h,
                price: (h.price / 31.1034768) * usdTry // Approximation using the current FX rate.
              })) : []
            };
          }

          setMarket(marketData)
        }
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
      setLoadingMore(false)
    }
  }

  useEffect(() => {
    fetchData(false)
  }, [assetFilter, sentimentFilter, showWatchlistOnly, watchlists])

  useEffect(() => {
    const interval = setInterval(() => fetchData(false), 60000)
    return () => clearInterval(interval)
  }, [assetFilter, sentimentFilter, showWatchlistOnly, watchlists])

  const total = news.length || 1
  const positive = news.filter(n => n.sentiment_label === 'positive').length
  const negative = news.filter(n => n.sentiment_label === 'negative').length
  const neutral = news.filter(n => n.sentiment_label === 'neutral').length

  const score = (positive - negative) / total
  let marketMood = "Nötr (Durağan)"
  let moodClass = "text-blue-400"

  if (score > 0.2) { marketMood = "Güçlü Boğa Piyasası"; moodClass = "text-green-400 glow-text-green" }
  else if (score < -0.2) { marketMood = "Riskli Ayı Piyasası"; moodClass = "text-red-400 glow-text-red" }

  const handleWatchlistToggle = async (e, assetType) => {
    e.preventDefault();
    if (!user) {
      setIsLoginModalOpen(true);
      return;
    }

    const existing = watchlists.find(w => w.asset_type === assetType);
    if (existing) {
      await removeFromWatchlist(existing.id);
    } else {
      await addToWatchlist(assetType);
    }
  };

  const isWatched = (assetType) => watchlists.some(w => w.asset_type === assetType);

  const openPortfolioEditor = (symbol, assetName, defaultTab = 'amount') => {
    if (!user) { setIsLoginModalOpen(true); return; }
    const quote = market?.[symbol];
    const fx = market?.USD_TRY;
    setPortfolioModalData({ symbol, assetName, defaultTab,
      currentPrice: quote?.available !== false && Number.isFinite(quote?.price) ? quote.price : 0,
      usdTryRate: fx?.available !== false && Number.isFinite(fx?.price) ? fx.price : 0 });
  };

  const renderTicker = (key, icon, label, prefix = "", assetType = "") => {
    if (!market || !market[key]) return null;
    const data = market[key];
    const available = data.available !== false && Number.isFinite(data.price) && data.price > 0;
    const hasChange = available && Number.isFinite(data.change_pct);
    const isUp = data.is_up;
    const colorClass = !hasChange ? "text-blue-400" : isUp ? "text-green-400 glow-text-green" : "text-red-400 glow-text-red";
    const Arrow = isUp ? "▲" : "▼";
    const formattedPrice = Number(data.price).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    const formattedPct = Math.abs(data.change_pct).toFixed(2);

    const chartData = data.history ? data.history.map((val, idx) => ({
      value: typeof val === 'object' && val !== null ? val.price : val,
      index: idx
    })) : [];
    const strokeColor = isUp ? "#4ade80" : "#f87171";

    const dbKey = key === "GRAM_GOLD" ? "GOLD" : key;
    const hasAsset = portfolio?.some(p => p.symbol === dbKey && p.amount > 0);

    return (
      <div className="ticker-item neon-border" key={key}>
        <div className="ticker-bg-chart">
          {chartData.length > 0 && (
            <ResponsiveContainer width="100%" height="100%">
              <RechartsLineChart data={chartData}>
                <YAxis domain={['auto', 'auto']} hide />
                <Line type="monotone" dataKey="value" stroke={strokeColor} strokeWidth={2} dot={false} isAnimationActive={false} />
              </RechartsLineChart>
            </ResponsiveContainer>
          )}
        </div>
        <div className="ticker-content-wrapper">
          {icon}
          <div className="ticker-info" style={{ flexGrow: 1 }}>
            <span className="ticker-name">{label}</span>
            <div className="ticker-values">
              <span className={`ticker-price ${colorClass}`}>{available ? `${prefix}${formattedPrice}` : 'Veri alınamadı'}</span>
              <span className={`ticker-pct ${colorClass}`}>{hasChange ? `${Arrow} %${formattedPct}` : 'Değişim verisi yok'}</span>
            </div>
          </div>
          {assetType && (
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <button
                className="watchlist-btn"
                disabled={dbKey === 'BIST100'}
                onClick={() => openPortfolioEditor(dbKey, key === "GRAM_GOLD" ? "Altın (ONS / Gram)" : label, key === "GRAM_GOLD" ? "try" : "amount")}
                title={dbKey === 'BIST100' ? 'Endeks doğrudan portföye eklenemez' : hasAsset ? "Portföyü Güncelle" : "Portföye Ekle"}
              >
                {hasAsset ? <Edit2 size={20} /> : <Plus size={20} />}
              </button>
              <button
                className={`watchlist-btn ${isWatched(dbKey) ? 'active' : ''}`}
                onClick={(e) => handleWatchlistToggle(e, dbKey)}
                title={isWatched(dbKey) ? "Takipten Çıkar" : "Takibe Al"}
              >
                {isWatched(dbKey) ? <BookmarkCheck size={20} /> : <Bookmark size={20} />}
              </button>
            </div>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="app-container">
      <LoginModal isOpen={isLoginModalOpen} onClose={() => setIsLoginModalOpen(false)} />
      {user && isPasswordModalOpen && (
        <ChangePasswordModal onClose={() => setIsPasswordModalOpen(false)} onSuccess={() => {
          setIsPasswordModalOpen(false)
          setAuthNotice('Şifreniz değiştirildi. Yeni şifrenizle tekrar giriş yapın.')
          setIsLoginModalOpen(true)
        }} />
      )}
      {portfolioModalData && (
        <PortfolioModal
          isOpen={true}
          onClose={() => setPortfolioModalData(null)}
          symbol={portfolioModalData.symbol}
          assetName={portfolioModalData.assetName}
          currentPrice={portfolioModalData.currentPrice}
          usdTryRate={portfolioModalData.usdTryRate}
          defaultTab={portfolioModalData.defaultTab}
        />
      )}

      <header className="glass-header">
        <div className="header-content">
          <div className="logo-section">
            <div className="logo-icon-wrapper">
              <Activity className="icon-pulse" size={28} color="#00ffcc" />
            </div>
            <h1>Finansal Duygu <span className="text-gradient">Motoru</span></h1>
          </div>

          <div className="auth-section">
            {user ? (
              <>
                <div className="user-email">
                  <User size={16} /> {user.first_name ? `${user.first_name} ${user.last_name}` : user.email}
                </div>
                <button className="auth-btn" onClick={() => setIsPasswordModalOpen(true)}>Şifre Değiştir</button>
                <button className="auth-btn" onClick={() => logout()}>
                  <LogOut size={16} /> Çıkış
                </button>
              </>
            ) : (
              <button className="auth-btn login-btn" onClick={() => setIsLoginModalOpen(true)}>
                <User size={16} /> Giriş Yap
              </button>
            )}
            <button className="refresh-btn glow-effect" onClick={() => fetchData(false)} disabled={loading}>
              <RefreshCw className={loading ? "spin" : ""} size={18} />
              <span className="hide-mobile">Yenile</span>
            </button>
          </div>
        </div>
      </header>

      <main className="dashboard">
        {authNotice.trim() && <p className="auth-notice" role="status">{authNotice}</p>}
        {user && portfolioReport && (
          <div className="portfolio-banner glass-panel premium-border" style={{ marginBottom: '2rem', padding: '2rem', display: 'flex', flexDirection: 'column', gap: '1.5rem', background: 'rgba(15, 23, 42, 0.6)' }}>
            <div className="portfolio-summary" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div>
                <p style={{ color: '#94a3b8', fontSize: '0.85rem', marginBottom: '0.5rem', textTransform: 'uppercase', letterSpacing: '1.5px', fontWeight: '600' }}>Toplam Varlığım</p>
                <h2 className="portfolio-total" style={{ fontSize: '3rem', color: '#fff', margin: 0, display: 'flex', alignItems: 'center', gap: '0.5rem', textShadow: '0 0 20px rgba(96, 165, 250, 0.3)' }}>
                  <DollarSign size={40} color="#60a5fa" />
                  {portfolioReport.total_value_usd != null ? portfolioReport.total_value_usd.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2}) : 'Hesaplanamadı'}
                </h2>
                <p style={{ color: '#4ade80', fontSize: '1.1rem', margin: '0.5rem 0 0 0', fontWeight: '500', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                  <span style={{opacity: 0.8}}>~ ₺</span>{portfolioReport.total_value_try != null ? portfolioReport.total_value_try.toLocaleString('tr-TR', {minimumFractionDigits: 2, maximumFractionDigits: 2}) : 'Hesaplanamadı'}
                </p>
              </div>
              <div className="portfolio-wallet" style={{ padding: '1rem', background: 'rgba(96, 165, 250, 0.1)', borderRadius: '16px', border: '1px solid rgba(96, 165, 250, 0.2)' }}>
                <Wallet size={48} color="#60a5fa" style={{ filter: 'drop-shadow(0 0 10px rgba(96, 165, 250, 0.5))' }} />
              </div>
            </div>
            {portfolioReport.items && portfolioReport.items.length > 0 && (
              <div className="portfolio-breakdown" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '1rem', marginTop: '0.5rem' }}>
                {portfolioReport.items.map(item => {
                  const isGold = item.symbol === 'GOLD';
                  const displaySymbol = isGold ? 'Altın (GOLD)' : item.symbol.replace('_', '/');

                  return (
                  <div key={item.symbol} className="portfolio-item glass-panel" style={{ padding: '1.25rem', borderRadius: '12px', display: 'flex', flexDirection: 'column', gap: '0.5rem', position: 'relative', transition: 'transform 0.2s', cursor: 'default' }} onMouseEnter={e => e.currentTarget.style.transform='translateY(-2px)'} onMouseLeave={e => e.currentTarget.style.transform='translateY(0)'}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        {isGold ? <Coins size={16} color="#fbbf24" /> : item.symbol === 'EUR_TRY' ? <Euro size={16} color="#60a5fa" /> : item.symbol === 'BTC' ? <Bitcoin size={16} /> : <DollarSign size={16} color="#4ade80" />}
                        <p style={{ margin: 0, color: '#e2e8f0', fontSize: '0.9rem', fontWeight: '600' }}>{displaySymbol}</p>
                      </div>
                      <div style={{ display: 'flex', gap: '0.5rem' }}>
                      {['USD_TRY', 'EUR_TRY', 'GOLD', 'BTC'].includes(item.symbol) && <button type="button" onClick={() => openPortfolioEditor(item.symbol, displaySymbol)} title="Varlığı Düzenle" aria-label={displaySymbol + ' miktarını düzenle'} style={{ background: 'transparent', border: 'none', color: '#60a5fa', cursor: 'pointer', padding: '0.3rem' }}><Edit2 size={18} /></button>}
                      <button
                        onClick={() => removeFromPortfolio(item.symbol)}
                        title="Varlığı Sil"
                        style={{ background: 'transparent', border: 'none', color: '#64748b', cursor: 'pointer', padding: '0.2rem', transition: 'color 0.2s' }}
                        onMouseEnter={(e) => { e.currentTarget.style.color = '#ef4444'; }}
                        onMouseLeave={(e) => { e.currentTarget.style.color = '#64748b'; }}
                      >
                        <Trash2 size={16} />
                      </button></div>
                    </div>
                    <div>
                      <h4 style={{ margin: '0.5rem 0 0 0', color: '#fff', fontSize: '1.4rem', fontWeight: '700' }}>
                        {item.amount.toLocaleString('en-US', {maximumFractionDigits: item.symbol === 'BTC' ? 8 : isGold ? 6 : 2})}
                        <span style={{fontSize: '0.8rem', color: '#94a3b8', fontWeight: 'normal', marginLeft: '4px'}}>{{ GOLD: 'ONS', USD_TRY: 'USD', EUR_TRY: 'EUR', BTC: 'BTC' }[item.symbol] || ''}</span>
                      </h4>
                      {isGold && (
                        <p style={{ margin: '0.2rem 0 0 0', color: '#fbbf24', fontSize: '0.8rem' }}>
                          ~ {(item.amount * 31.1034768).toLocaleString('en-US', {maximumFractionDigits: 2})} Gram
                        </p>
                      )}
                    </div>
                    <div style={{ marginTop: 'auto', paddingTop: '0.75rem', borderTop: '1px solid rgba(255,255,255,0.05)' }}>
                      <p style={{ margin: 0, color: '#4ade80', fontSize: '1rem', fontWeight: '600' }}>
                        {item.value != null ? `$${item.value.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})}` : item.valuation_status === 'unsupported_asset' ? 'Değerleme desteklenmiyor' : 'Fiyat alınamadı'}
                      </p>
                      {item.value_try != null && (
                        <p style={{ margin: 0, color: '#94a3b8', fontSize: '0.85rem' }}>
                          ~ ₺{item.value_try.toLocaleString('tr-TR', {minimumFractionDigits: 2, maximumFractionDigits: 2})}
                        </p>
                      )}
                    </div>
                  </div>
                )})}
              </div>
            )}
            {portfolioReport.items?.length > 0 && (
              <div className="risk-report glass-panel" style={{ marginTop: '0.5rem', padding: '1.25rem', borderRadius: '12px', border: '1px solid rgba(251, 191, 36, 0.3)', display: 'flex', gap: '1rem', alignItems: 'flex-start', background: 'linear-gradient(90deg, rgba(251, 191, 36, 0.05) 0%, transparent 100%)' }}>
                <div style={{ background: 'rgba(251, 191, 36, 0.1)', padding: '0.5rem', borderRadius: '8px' }}>
                  <ShieldAlert size={24} color="#fbbf24" style={{ filter: 'drop-shadow(0 0 8px rgba(251, 191, 36, 0.5))' }} />
                </div>
                <div>
                  <h4 style={{ margin: '0 0 0.5rem 0', color: '#fbbf24', fontSize: '1rem', fontWeight: '600', letterSpacing: '0.5px' }}>Portföy Haber Duygusu ve Değerleme</h4>
                  <p style={{ margin: 0, color: '#cbd5e1', lineHeight: '1.6', fontSize: '0.95rem' }}>{portfolioReport.report_text}</p>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Market Ticker Section */}
        <div className="market-ticker glass-panel">
          {renderTicker("USD_TRY", <DollarSign size={24} color="#4ade80" className="drop-shadow-green"/>, "USD/TRY", "₺", "GENERAL")}
              {renderTicker("EUR_TRY", <Euro size={24} color="#60a5fa" />, "EUR/TRY", "₺", "GENERAL")}
          {renderTicker("GOLD", <Coins size={24} color="#fbbf24" style={{filter: 'drop-shadow(0 0 8px rgba(251, 191, 36, 0.4))'}}/>, "Altın (ONS)", "$", "GENERAL")}
          {renderTicker("GRAM_GOLD", <Gem size={24} color="#fbbf24" style={{filter: 'drop-shadow(0 0 8px rgba(251, 191, 36, 0.4))'}}/>, "Gram Altın", "₺", "GENERAL")}
          {renderTicker("BTC", <Bitcoin size={24} color="#f7931a" style={{filter: 'drop-shadow(0 0 8px rgba(247, 147, 26, 0.4))'}}/>, "Bitcoin", "$", "CRYPTO")}
          {renderTicker("BIST100", <LineChart size={24} color="#f87171" className="drop-shadow-red"/>, "BIST 100", "", "GENERAL")}
        </div>

        <div className="stats-row">
          <div className="stat-card glass-panel premium-border">
            <h3>Yapay Zeka Piyasa Beklentisi</h3>
            <div className={`mood-score ${moodClass}`}>{marketMood}</div>
            <p className="subtitle">Listelenen {news.length} habere göre</p>
          </div>

          <div className="stat-card glass-panel flex-row">
            <div className="stat-item hover-scale">
              <TrendingUp color="#4ade80" size={32} className="drop-shadow-green"/>
              <span className="stat-value text-green-400 glow-text-green">{positive}</span>
              <span className="stat-label">Olumlu Sinyal</span>
            </div>
            <div className="stat-item hover-scale">
              <TrendingDown color="#f87171" size={32} className="drop-shadow-red"/>
              <span className="stat-value text-red-400 glow-text-red">{negative}</span>
              <span className="stat-label">Olumsuz Sinyal</span>
            </div>
            <div className="stat-item hover-scale">
              <Minus color="#60a5fa" size={32} className="drop-shadow-blue"/>
              <span className="stat-value text-blue-400 glow-text-blue">{neutral}</span>
              <span className="stat-label">Nötr</span>
            </div>
          </div>
        </div>

        <CorrelationChart />

        <div className="section-header">
          <h2 className="section-title">Canlı Haber Akışı ve NLP Analizi</h2>

          <div className="filters-container">
            {user && (
              <div
                className={`watchlist-toggle-wrapper ${showWatchlistOnly ? 'active' : ''}`}
                onClick={() => setShowWatchlistOnly(!showWatchlistOnly)}
              >
                {showWatchlistOnly ? <BookmarkCheck size={16} color="#fbbf24" /> : <Bookmark size={16} color="#94a3b8" />}
                <span style={{ color: showWatchlistOnly ? '#fbbf24' : '#94a3b8', fontSize: '0.9rem' }}>
                  Sadece Takip Ettiklerim
                </span>
              </div>
            )}

            <div className="filter-group">
              <Filter size={16} color="#94a3b8" />
              <select value={assetFilter} onChange={(e) => setAssetFilter(e.target.value)} className="glass-select" disabled={showWatchlistOnly}>
                <option value="">Tüm Varlıklar</option>
                <option value="GENERAL">Borsa & Ekonomi</option>
                <option value="CRYPTO">Kripto Para</option>
              </select>
            </div>
            <div className="filter-group">
              <select value={sentimentFilter} onChange={(e) => setSentimentFilter(e.target.value)} className="glass-select">
                <option value="">Tüm Sinyaller</option>
                <option value="positive">Sadece Olumlu</option>
                <option value="negative">Sadece Olumsuz</option>
                <option value="neutral">Sadece Nötr</option>
              </select>
            </div>
          </div>
        </div>

        {error && <div className="error-box glass-panel">Bağlantı Hatası: {error}</div>}

        <div className="news-grid">
          {loading && news.length === 0 ? (
            <div className="loading-state">
              <Activity className="spin" size={48} color="#00ffcc" />
              <p>Yapay Zeka verileri derliyor, lütfen bekleyin...</p>
            </div>
          ) : news.length === 0 ? (
            <div className="loading-state">
              <p>{showWatchlistOnly && watchlists.length === 0 ? "Takip listeniz boş. Yukarıdan varlıkları takibe alabilirsiniz." : "Bu filtrelere uygun haber bulunamadı."}</p>
            </div>
          ) : (
            news.map((item) => (
              <a href={item.url} target="_blank" rel="noreferrer" key={item.id} className={`news-card glass-panel border-${item.sentiment_label}`}>
                <div className="news-meta">
                  <span className="source-tag">{item.source.toUpperCase()}</span>
                  <span className="time-tag">{new Date(item.published_at).toLocaleTimeString('tr-TR')}</span>
                  {user && (
                    <button
                      className={`watchlist-btn ${isWatched(item.asset_type) ? 'active' : ''}`}
                      onClick={(e) => handleWatchlistToggle(e, item.asset_type)}
                      style={{ marginLeft: 'auto' }}
                    >
                      {isWatched(item.asset_type) ? <BookmarkCheck size={16} /> : <Bookmark size={16} />}
                    </button>
                  )}
                </div>
                <h3 className="news-title">{item.title}</h3>
                <div className="news-footer">
                  <span className={`sentiment-badge bg-${item.sentiment_label}`}>
                    {item.sentiment_label === 'positive' && <TrendingUp size={14}/>}
                    {item.sentiment_label === 'negative' && <TrendingDown size={14}/>}
                    {item.sentiment_label === 'neutral' && <Minus size={14}/>}
                    {item.sentiment_label.toUpperCase()}
                  </span>
                  <span className="score-text">AI Güven Skoru: <span className="font-bold">%{(item.sentiment_score * 100).toFixed(1)}</span></span>
                </div>
              </a>
            ))
          )}
        </div>

        {!loading && hasMore && news.length > 0 && !showWatchlistOnly && (
          <div className="load-more-container">
            <button className="load-more-btn glow-effect" onClick={() => fetchData(true)} disabled={loadingMore}>
              {loadingMore ? <Activity className="spin" size={18} /> : <span>Daha Fazla Yükle</span>}
            </button>
          </div>
        )}
      </main>

      <ChatbotWidget />

      <footer className="app-footer">
        <p>Powered by <span className="author-name">Doğukan KILIÇ</span></p>
      </footer>
    </div>
  )
}

function App() {
  return (
    <AuthProvider>
      <Dashboard />
    </AuthProvider>
  )
}

export default App
