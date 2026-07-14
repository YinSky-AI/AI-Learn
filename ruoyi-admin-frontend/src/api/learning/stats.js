import request from '@/utils/request'

// 查询概览数据
export function getOverview() {
  return request({
    url: '/learning/stats/overview',
    method: 'get'
  })
}

// 查询每日活跃用户
export function getDailyActive(query) {
  return request({
    url: '/learning/stats/daily-active',
    method: 'get',
    params: query
  })
}

// 查询课程报名排行
export function getCourseRanking(query) {
  return request({
    url: '/learning/stats/course-ranking',
    method: 'get',
    params: query
  })
}

// 查询学科分布
export function getSubjectDist() {
  return request({
    url: '/learning/stats/subject-dist',
    method: 'get'
  })
}