import React, { createContext, useState, useEffect } from 'react';

export const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(localStorage.getItem('token') || null);
  const [watchlists, setWatchlists] = useState([]);
  const [portfolio, setPortfolio] = useState([]);
  const [portfolioReport, setPortfolioReport] = useState(null);

  useEffect(() => {
    if (token) {
      localStorage.setItem('token', token);
      fetchUser();
      fetchWatchlists();
      fetchPortfolio();
      fetchPortfolioReport();
    } else {
      localStorage.removeItem('token');
      setUser(null);
      setWatchlists([]);
      setPortfolio([]);
      setPortfolioReport(null);
    }
  }, [token]);

  const fetchUser = async () => {
    try {
      const response = await fetch('/api/auth/me', {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (response.ok) {
        const data = await response.json();
        setUser(data);
      } else {
        logout();
      }
    } catch (err) {
      console.error(err);
    }
  };

  const fetchWatchlists = async () => {
    try {
      const response = await fetch('/api/watchlist/', {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (response.ok) {
        const data = await response.json();
        setWatchlists(data);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const fetchPortfolio = async () => {
    try {
      const response = await fetch('/api/portfolio/', {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (response.ok) {
        const data = await response.json();
        setPortfolio(data);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const fetchPortfolioReport = async () => {
    try {
      const response = await fetch('/api/portfolio/report', {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (response.ok) {
        const data = await response.json();
        setPortfolioReport(data);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const setPortfolioItem = async (symbol, amount) => {
    try {
      const response = await fetch('/api/portfolio/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({ symbol, amount: parseFloat(amount) })
      });
      if (response.ok) {
        await fetchPortfolio();
        await fetchPortfolioReport();
        return true;
      }
      return false;
    } catch (err) {
      console.error("Set portfolio error", err);
      return false;
    }
  };

  const removeFromPortfolio = async (symbol) => {
    if (!token) return;
    try {
      const response = await fetch(`/api/portfolio/${symbol}`, {
        method: 'DELETE',
        headers: {
          Authorization: `Bearer ${token}`
        }
      });
      if (response.ok) {
        await fetchPortfolio();
        await fetchPortfolioReport();
      }
    } catch (err) {
      console.error("Remove from portfolio error", err);
    }
  };

  const login = async (email, password) => {
    try {
      const formData = new URLSearchParams();
      formData.append('username', email);
      formData.append('password', password);

      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: formData
      });
      
      if (res.ok) {
        const data = await res.json();
        setToken(data.access_token);
        return true;
      }
      return false;
    } catch (err) {
      console.error("Login fetch error:", err);
      return false;
    }
  };

  const register = async (email, password, firstName, lastName) => {
    try {
      const res = await fetch('/api/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password, first_name: firstName, last_name: lastName })
      });
      
      if (res.ok) {
        return await login(email, password);
      }
      return false;
    } catch (err) {
      console.error("Register fetch error:", err);
      return false;
    }
  };

  const logout = () => {
    setToken(null);
  };

  const addToWatchlist = async (assetType) => {
    const res = await fetch('/api/watchlist/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`
      },
      body: JSON.stringify({ asset_type: assetType })
    });
    
    if (res.ok) {
      fetchWatchlists();
      return true;
    }
    return false;
  };

  const removeFromWatchlist = async (id) => {
    const res = await fetch(`/api/watchlist/${id}`, {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${token}` }
    });
    
    if (res.ok) {
      fetchWatchlists();
    }
  };

  return (
    <AuthContext.Provider value={{ user, token, watchlists, portfolio, portfolioReport, setPortfolioItem, removeFromPortfolio, login, register, logout, addToWatchlist, removeFromWatchlist }}>
      {children}
    </AuthContext.Provider>
  );
};
