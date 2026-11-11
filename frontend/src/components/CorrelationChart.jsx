import { useState, useEffect } from 'react';
import { ComposedChart, Line, Area, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { Activity } from 'lucide-react';

const CorrelationChart = () => {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [symbol, setSymbol] = useState("BTC");

  useEffect(() => {
    const fetchCorrelation = async () => {
      setLoading(true);
      setError(null);
      try {
        const response = await fetch(`/api/correlation/${symbol}`);
        if (!response.ok) {
          throw new Error('Korelasyon verisi çekilemedi.');
        }
        const result = await response.json();
        // Result: { symbol: "...", asset_type: "...", data: [ {date, timestamp, price, sentiment_score}, ... ] }
        setData(result.data || []);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchCorrelation();
  }, [symbol]);

  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      return (
        <div className="glass-panel" style={{ padding: '10px', border: '1px solid rgba(255,255,255,0.1)' }}>
          <p className="label" style={{ color: '#fff', marginBottom: '5px' }}>{`${label}`}</p>
          {payload.map((entry, index) => (
            <p key={`item-${index}`} style={{ color: entry.color, margin: 0, fontSize: '14px' }}>
              {`${entry.name}: ${entry.name === 'Fiyat' ? (symbol === 'USD_TRY' ? '₺' : symbol === 'BIST100' ? '' : '$') : ''}${Number(entry.value).toLocaleString('en-US', {maximumFractionDigits:2})}`}
            </p>
          ))}
        </div>
      );
    }
    return null;
  };

  return (
    <div className="comparison-panel glass-panel" style={{ marginTop: '2rem', padding: '1.5rem' }}>
      <div className="comparison-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
        <h3 style={{ margin: 0, fontSize: '1.2rem', color: '#fff', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Activity size={20} color="#00ffcc" />
          Haber Duygusu ve Fiyat Karşılaştırması
        </h3>
        <select 
          value={symbol} 
          onChange={(e) => setSymbol(e.target.value)}
          className="glass-select"
          style={{ padding: '0.5rem 1rem', fontSize: '0.9rem' }}
        >
          <option value="BTC">Bitcoin (Kripto)</option>
          <option value="BIST100">BIST 100 (Ekonomi)</option>
          <option value="GOLD">Altın ONS (Ekonomi)</option>
          <option value="USD_TRY">Dolar/TL (Ekonomi)</option>
        </select>
      </div>

      {loading ? (
        <div className="loading-state" style={{ height: '300px' }}>
          <Activity className="spin" size={32} color="#00ffcc" />
          <p>Karşılaştırma verisi yükleniyor...</p>
        </div>
      ) : error ? (
        <div className="error-box glass-panel" style={{ height: '300px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          Bağlantı Hatası: {error}
        </div>
      ) : data.length === 0 ? (
        <div className="loading-state" style={{ height: '300px' }}>
          <p>Yeterli veri bulunamadı.</p>
        </div>
      ) : (
        <div className="comparison-plot" style={{ width: '100%', height: '350px' }}>
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart
              data={data}
              margin={{ top: 20, right: 20, bottom: 20, left: 20 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
              
              <XAxis 
                dataKey="date" 
                stroke="#94a3b8" 
                tick={{fill: '#94a3b8', fontSize: 12}} 
                tickMargin={10} 
                minTickGap={20}
              />
              
              {/* Sol Eksen: Fiyat */}
              <YAxis 
                yAxisId="left" 
                orientation="left" 
                stroke="#60a5fa" 
                domain={['auto', 'auto']}
                tickFormatter={(val) => val >= 1000 ? `${(val/1000).toFixed(1)}k` : val}
                tick={{fill: '#60a5fa', fontSize: 12}}
              />
              
              {/* Sağ Eksen: Duygu Skoru (-1 ile +1) */}
              <YAxis 
                yAxisId="right" 
                orientation="right" 
                stroke="#f59e0b" 
                domain={[-1, 1]} 
                tick={{fill: '#f59e0b', fontSize: 12}}
              />
              
              <Tooltip content={<CustomTooltip />} />
              <Legend wrapperStyle={{ paddingTop: '20px' }}/>
              
              {/* Duygu Skoru (Alan Grafiği olarak) */}
              <Area 
                yAxisId="right" 
                type="monotone" 
                dataKey="sentiment_score" 
                name="NLP Duygu Skoru" 
                fill="rgba(245, 158, 11, 0.15)" 
                stroke="#f59e0b" 
                strokeWidth={2}
              />

              {/* Fiyat (Çizgi Grafiği olarak) */}
              <Line 
                yAxisId="left" 
                type="monotone" 
                dataKey="price" 
                name="Fiyat" 
                stroke="#60a5fa" 
                strokeWidth={3} 
                dot={false}
                activeDot={{ r: 6 }}
              />
              
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
};

export default CorrelationChart;
