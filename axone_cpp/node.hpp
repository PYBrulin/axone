#include <random>
#include <algorithm>
#include <string>

#include "json.hpp"

using json::JSON;

class Node
{
private:
    std::string node_id;

    std::string _get_node_id()
    {
        std::string chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
        std::random_device rd;
        std::mt19937 generator(rd());

        std::shuffle(chars.begin(), chars.end(), generator);

        return chars.substr(0, 10); // Return the first 10 characters
    }

    /*! Try to get lock. Return its file descriptor or -1 if failed.
     *
     *  @param lockName Name of file used as lock (i.e. '/var/lock/myLock').
     *  @return File descriptor of lock file, or -1 if failed.
     */
    int tryGetLock(char const *lockName)
    {
        mode_t m = umask(0);
        int fd = open(lockName, O_RDWR | O_CREAT, 0666);
        umask(m);
        if (fd >= 0 && flock(fd, LOCK_EX | LOCK_NB) < 0)
        {
            close(fd);
            fd = -1;
        }
        return fd;
    }

    /*! Release the lock obtained with tryGetLock( lockName ).
     *
     *  @param fd File descriptor of lock returned by tryGetLock( lockName ).
     *  @param lockName Name of file used as lock (i.e. '/var/lock/myLock').
     */
    void releaseLock(int fd, char const *lockName)
    {
        if (fd < 0)
            return;
        remove(lockName);
        close(fd);
    }


public:
    JSON readJsonFile(const std::string &filename, char const *lockName)
    {
        int fd = tryGetLock(lockName);
        while (fd != -1)
        {
            std::ifstream file(filename, std::ifstream::binary);
            if (!file.is_open())
            {
                std::cerr << "Error: Unable to open file " << filename << std::endl;
                releaseLock(fd, lockName);
                return JSON::Load("{}"); // Empty JSON object
            }

            // Get the content of the file
            std::string content((std::istreambuf_iterator<char>(file)),
                                (std::istreambuf_iterator<char>()));

            // std::cout << "Content: " << content << std::endl;

            // Parse the content
            // TODO: Use the stream directly instead of copying the content?
            JSON obj = JSON::Load(content);

            releaseLock(fd, lockName);
            return obj;
        }
    }

};
