#include <iostream>
#include <sys/types.h>
#include <sys/stat.h>
#include <sys/file.h>
#include <fcntl.h>
#include <fstream>
#include <thread>
#include <chrono>
#include <unistd.h>

#include "json.hpp"
#include "node.hpp"


int main(int argc, char *argv[])
{
    if (argc != 2)
    {
        std::cerr << "Error: Invalid number of arguments. Usage: axone_cpp <memory_name>" << std::endl;
        return 1;
    }

    // Load the name of the memory from the command line
    const std::string memoryName = argv[1];
    std::string result = std::string("/home/hexadrone-dev/") + memoryName + std::string(".axone.lock");
    const char *lockName = result.c_str();

    const std::string jsonFilename = "/dev/shm/sm_" + memoryName;
    const int readRateHertz = 5;

    // Create Node
    Node axone_node;

    while (true)
    {
        // Clear the terminal before displaying the data
        std::cout << "\033[2J\033[1;1H";

        // Json::Value jsonData =
        JSON obj = axone_node.readJsonFile(jsonFilename, lockName);

        // // Display the data
        // std::cout << "Data: " << std::endl;
        // std::cout << obj << std::endl;

        // Try to iterate over the nodes and display their names
        // std::cout << "Nodes: " << std::endl;
        // for (auto &node : obj["__nds"].ObjectRange())
        // {
        //     std::cout << node.first << " : " << node.second["__n"] << std::endl;
        // }

        std::cout << "Node ID: " << axone_node.find_node_id_by_name(obj, "example_publisher") << " for node example_publisher" << std::endl;

        std::cout << "Services: " << std::endl;
        for (auto &service : obj["__srv"].ArrayRange())
        {
            std::cout << service["__dst"] << " -> " << service["__dst"] << ": ";
            for (auto &property : service.ObjectRange())
            {
                // if start with __, it's a special property
                if (property.first.find("__") == 0)
                    continue;
                // std::cout << property.first << " : " << property.second << std::endl;
                std::cout << property.first << std::endl;
            }
        }

        std::cout << "Topics: " << std::endl;
        for (auto &topic : obj.ObjectRange())
        {
            // if start with __, it's a special property
            if (topic.first.find("__") == 0)
                continue;
            std::cout << topic.first << " (" << topic.second["__r"] << " Hz)" << std::endl;
        }

        // Save the object to a local file
        std::ofstream file("data.json");
        file << obj.dump(1, "", ",", ":", false);
        file.close();


        // Wait for the next iteration
        std::this_thread::sleep_for(std::chrono::milliseconds(1000 / readRateHertz));
    }
}
