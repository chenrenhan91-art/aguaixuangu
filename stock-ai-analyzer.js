/**
 * Make.com 股票交易 AI 分析集成
 * 简易版 - 可直接在 HTML 中使用
 */

class StockAIAnalyzer {
  constructor(webhookUrl = 'https://hook.us2.make.com/gav22ypjvftehn5uvqt4hduwzlmvs8fj') {
    this.webhookUrl = webhookUrl;
    this.analyzing = false;
  }

  /**
   * 发送数据到 Make.com webhook 进行 AI 分析
   */
  async analyze(stockData) {
    if (this.analyzing) {
      throw new Error('分析正在进行中，请稍候...');
    }

    this.analyzing = true;

    try {
      const payload = {
        symbol: stockData.symbol || '',
        stock_name: stockData.stock_name || '',
        current_price: parseFloat(stockData.current_price) || 0,
        stop_loss_price: parseFloat(stockData.stop_loss_price) || 0,
        take_profit_1: parseFloat(stockData.take_profit_1) || 0,
        take_profit_2: parseFloat(stockData.take_profit_2) || 0,
        risk_reward_ratio: parseFloat(stockData.risk_reward_ratio) || 0,
        volatility_10: parseFloat(stockData.volatility_10) || 0,
        industry: stockData.industry || '',
        event_text: stockData.event_text || '',
        mode_id: stockData.mode_id || 'neutral',
        user_id: stockData.user_id || null,
        trade_date: stockData.trade_date || new Date().toISOString().split('T')[0]
      };

      const response = await fetch(this.webhookUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
        body: JSON.stringify(payload),
        mode: 'cors',
      });

      if (!response.ok) {
        throw new Error(`请求失败: ${response.status} ${response.statusText}`);
      }

      const responseText = await response.text();
      
      return {
        success: true,
        status: 'submitted',
        message: '分析请求已成功提交至 Gemini AI',
        timestamp: new Date().toISOString(),
        data: stockData
      };

    } catch (error) {
      console.error('分析错误:', error);
      return {
        success: false,
        error: error.message,
        timestamp: new Date().toISOString()
      };
    } finally {
      this.analyzing = false;
    }
  }

  /**
   * 表单数据转换
   */
  static formToData(formElement) {
    const formData = new FormData(formElement);
    return {
      symbol: formData.get('symbol'),
      stock_name: formData.get('stock_name'),
      current_price: formData.get('current_price'),
      stop_loss_price: formData.get('stop_loss_price'),
      take_profit_1: formData.get('take_profit_1'),
      take_profit_2: formData.get('take_profit_2'),
      risk_reward_ratio: formData.get('risk_reward_ratio'),
      volatility_10: formData.get('volatility_10'),
      industry: formData.get('industry'),
      event_text: formData.get('event_text'),
      mode_id: formData.get('mode_id') || 'neutral'
    };
  }
}

// 使用示例
// const analyzer = new StockAIAnalyzer();
// const result = await analyzer.analyze({ symbol: '603629', stock_name: '利通电子', ... });
// console.log(result);

// 导出供 ES6 模块使用
if (typeof module !== 'undefined' && module.exports) {
  module.exports = StockAIAnalyzer;
}
