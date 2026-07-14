import request from '@/utils/request'

// 查询课程列表
export function listCourse(query) {
  return request({
    url: '/learning/course/list',
    method: 'get',
    params: query
  })
}

// 查询课程详细
export function getCourse(courseId) {
  return request({
    url: '/learning/course/' + courseId,
    method: 'get'
  })
}

// 修改课程状态
export function changeCourseStatus(data) {
  return request({
    url: '/learning/course/status',
    method: 'put',
    data: data
  })
}

// 删除课程
export function delCourse(courseId) {
  return request({
    url: '/learning/course/' + courseId,
    method: 'delete'
  })
}