// utils/api.js - API 请求封装

const app = getApp();

/**
 * 发送 Agent 请求
 * @param {string} userInput - 用户输入
 * @param {string} sessionId - 会话 ID（可选）
 * @returns {Promise}
 */
function executeAgent(userInput, sessionId) {
  return new Promise((resolve, reject) => {
    wx.request({
      url: `${app.globalData.baseUrl}/api/agent/execute`,
      method: 'POST',
      header: {
        'Content-Type': 'application/json'
      },
      data: {
        userInput: userInput,
        sessionId: sessionId || app.globalData.sessionId,
        userId: app.globalData.userInfo?.userId
      },
      success(res) {
        if (res.statusCode === 200) {
          const data = res.data;

          // 保存会话 ID
          if (data.sessionId) {
            app.globalData.sessionId = data.sessionId;
          }

          resolve(data);
        } else {
          reject(new Error(`请求失败: ${res.statusCode}`));
        }
      },
      fail(err) {
        reject(err);
      }
    });
  });
}

/**
 * 确认/取消方案
 * @param {string} sessionId - 会话 ID
 * @param {boolean} confirmed - 是否确认
 * @returns {Promise}
 */
function confirmPlan(sessionId, confirmed) {
  return new Promise((resolve, reject) => {
    wx.request({
      url: `${app.globalData.baseUrl}/api/agent/confirm`,
      method: 'POST',
      header: {
        'Content-Type': 'application/json'
      },
      data: {
        sessionId: sessionId,
        confirmed: confirmed
      },
      success(res) {
        if (res.statusCode === 200) {
          resolve(res.data);
        } else {
          reject(new Error(`确认请求失败: ${res.statusCode}`));
        }
      },
      fail(err) {
        reject(err);
      }
    });
  });
}

/**
 * 多轮对话：识别修改意图 → 局部 patch；否则普通对话回复
 * @param {string} userInput - 用户输入
 * @param {string} sessionId - 会话 ID（必传，必须已有 plan）
 * @returns {Promise<{status:string, sessionId:string, actionType?:string,
 *   changeLog?:Array, planSummary?:string, reply?:string, route?:Array,
 *   routeStats?:Object, story?:Object, tasks?:Array}>}
 */
function continueConversation(userInput, sessionId) {
  return new Promise((resolve, reject) => {
    wx.request({
      url: `${app.globalData.baseUrl}/api/agent/continue`,
      method: 'POST',
      header: {
        'Content-Type': 'application/json'
      },
      data: {
        userInput: userInput,
        sessionId: sessionId || app.globalData.sessionId
      },
      success(res) {
        if (res.statusCode === 200) {
          const data = res.data;
          if (data.sessionId) {
            app.globalData.sessionId = data.sessionId;
          }
          resolve(data);
        } else {
          reject(new Error(`多轮对话请求失败: ${res.statusCode}`));
        }
      },
      fail(err) {
        reject(err);
      }
    });
  });
}

/**
 * 健康检查
 * @returns {Promise}
 */
function healthCheck() {
  return new Promise((resolve, reject) => {
    wx.request({
      url: `${app.globalData.baseUrl}/api/agent/health`,
      method: 'GET',
      success(res) {
        if (res.statusCode === 200) {
          resolve(res.data);
        } else {
          reject(new Error(`健康检查失败: ${res.statusCode}`));
        }
      },
      fail(err) {
        reject(err);
      }
    });
  });
}

module.exports = {
  executeAgent,
  confirmPlan,
  continueConversation,
  healthCheck
};
